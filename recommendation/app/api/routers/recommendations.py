import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.optimization.idle_mitigation import score_idle_mitigation_opportunities
from app.optimization.recommendation_service import RecommendationService
from app.schemas.recommendation import (
    BatchRecommendationRequest,
    IdleMitigationRequest,
    RecommendationRequest,
    RecommendationResponse,
)

router = APIRouter(prefix="/recommend", tags=["Recommendation & Optimization Engine"])

# In-memory job status store for standalone/synchronous execution mode (USE_CELERY=False),
# mirroring the pattern already used by app/api/routers/forecasts.py's training jobs.
BATCH_JOB_STORE: Dict[str, Dict[str, Any]] = {}


@router.post("", response_model=RecommendationResponse)
def get_chartering_recommendation(
    request: RecommendationRequest,
    db: Session = Depends(get_db)
) -> RecommendationResponse:
    """
    Inputs cargo requirements (commodity, quantity MT, destination port, laycan window).
    Solves port depth/LOA physical feasibility constraints, retrieves Phase 3 AI rate forecasts,
    and returns optimal origin port, vessel class, landed cost, charter scenarios, and risk flags.
    """
    try:
        svc = RecommendationService(db)
        rec = svc.generate_recommendation(
            commodity=request.commodity,
            cargo_qty_mt=request.cargo_qty_mt,
            destination_port_code=request.destination_port_code,
            laycan_start=request.laycan_start,
            laycan_end=request.laycan_end
        )
        return rec
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation engine error: {e}")


@router.post("/batch", status_code=202)
def submit_batch_recommendation(
    request: BatchRecommendationRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Multi-parcel chartering optimization (Phase 4 "full solver"). Runs the CP-SAT
    MILP over the whole parcel book, so cross-parcel constraints (SpotCapRatio,
    per-port throughput capacity) can bind. Executes inline for small parcel books;
    routes through Celery (or an in-memory job store when USE_CELERY is False) for
    larger books or when `full_optimization=true`, per the roadmap's requirement that
    the full multi-parcel solve must never block the request thread.
    """
    parcels = [p.model_dump() for p in request.parcels]
    if not parcels:
        raise HTTPException(status_code=400, detail="At least one parcel is required.")

    run_async = request.full_optimization or len(parcels) > settings.FULL_OPTIMIZATION_PARCEL_THRESHOLD
    job_id = str(uuid.uuid4())

    if not run_async:
        try:
            svc = RecommendationService(db)
            result = svc.generate_multi_parcel_recommendation(parcels=parcels, spot_cap_ratio=request.spot_cap_ratio)
            return {"job_id": job_id, "status": "SUCCESS", "mode": "SYNC", "result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Batch optimization error: {e}")

    if settings.USE_CELERY:
        from app.worker import run_batch_optimization_task
        # Celery's json serializer can't handle `date` objects - hand it the same
        # dicts but with dates coerced to ISO strings.
        serializable_parcels = [
            {**p, "laycan_start": p["laycan_start"].isoformat(), "laycan_end": p["laycan_end"].isoformat()}
            for p in parcels
        ]
        run_batch_optimization_task.apply_async(
            kwargs={"parcels": serializable_parcels, "spot_cap_ratio": request.spot_cap_ratio},
            task_id=job_id,
        )
        return {"job_id": job_id, "status": "PENDING", "mode": "CELERY", "message": "Full multi-parcel optimization submitted to Celery queue."}

    # In-memory execution fallback (USE_CELERY=False, but full_optimization requested/needed)
    BATCH_JOB_STORE[job_id] = {"status": "RUNNING", "result": None}
    try:
        svc = RecommendationService(db)
        result = svc.generate_multi_parcel_recommendation(parcels=parcels, spot_cap_ratio=request.spot_cap_ratio)
        BATCH_JOB_STORE[job_id] = {"status": "SUCCESS", "result": result}
    except Exception as e:
        BATCH_JOB_STORE[job_id] = {"status": "FAILURE", "error": str(e)}
    return {"job_id": job_id, "mode": "IN_MEMORY", **BATCH_JOB_STORE[job_id]}


@router.get("/batch/jobs/{job_id}")
def get_batch_job_status(job_id: str) -> Dict[str, Any]:
    """Polls the status of an asynchronous multi-parcel optimization job."""
    if settings.USE_CELERY:
        from app.worker import celery_app
        res = celery_app.AsyncResult(job_id)
        return {"job_id": job_id, "status": res.status, "result": res.result if res.ready() else None}

    if job_id not in BATCH_JOB_STORE:
        raise HTTPException(status_code=404, detail="Job ID not found.")
    return {"job_id": job_id, **BATCH_JOB_STORE[job_id]}


@router.post("/idle-mitigation")
def get_idle_mitigation_suggestions(request: IdleMitigationRequest) -> Dict[str, Any]:
    """
    Section 3.3 heuristic: ranks open cargo / backhaul opportunities for a vessel that
    is forecast to be idle or ballasting. Recommendation surface only - never auto-commits.
    """
    suggestions = score_idle_mitigation_opportunities(
        idle_vessel_class_name=request.vessel_class_name,
        idle_position_port_code=request.idle_position_port_code,
        idle_days_available=request.idle_days_available,
        bunker_consumption_tpd=request.bunker_consumption_tpd,
        open_opportunities=[o.model_dump() for o in request.open_opportunities],
        top_n=request.top_n,
    )
    return {"idle_position_port_code": request.idle_position_port_code, "suggestions": suggestions}





