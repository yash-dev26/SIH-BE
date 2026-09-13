import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ModelRegistry
from app.db.session import get_db
from app.forecasting.inference_service import ForecastingService
from app.forecasting.training_job import run_model_training_pipeline
from app.schemas.forecast import (
    ForecastRequest,
    ForecastResult,
    ModelRegistryResponse,
    ModelTrainRequest,
)

router = APIRouter(prefix="/forecasts", tags=["Forecasts & Models"])

# In-memory job status store for standalone/synchronous execution mode
JOB_STORE: Dict[str, Dict[str, Any]] = {}


@router.post("/models/train", status_code=202)
def train_models(
    request: ModelTrainRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Enqueues an asynchronous model training pipeline job for specified trade lanes and vessel classes.
    """
    job_id = str(uuid.uuid4())

    if settings.USE_CELERY:
        from app.worker import train_models_task
        task = train_models_task.apply_async(
            kwargs={
                "trade_lane_ids": request.trade_lane_ids,
                "vessel_class_ids": request.vessel_class_ids,
                "target_variable": request.target_variable,
            },
            task_id=job_id
        )
        return {"job_id": job_id, "status": "PENDING", "message": "Training job submitted to Celery queue."}
    else:
        # In-memory execution fallback
        JOB_STORE[job_id] = {"status": "RUNNING", "result": None}
        try:
            res = run_model_training_pipeline(
                db=db,
                trade_lane_ids=request.trade_lane_ids,
                vessel_class_ids=request.vessel_class_ids,
                target_variable=request.target_variable
            )
            JOB_STORE[job_id] = {"status": "SUCCESS", "result": res}
            return {"job_id": job_id, "status": "SUCCESS", "result": res}
        except Exception as e:
            JOB_STORE[job_id] = {"status": "FAILURE", "error": str(e)}
            raise HTTPException(status_code=500, detail=f"Training failed: {e}")


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Polls the status of an asynchronous model training job.
    """
    if settings.USE_CELERY:
        from app.worker import celery_app
        res = celery_app.AsyncResult(job_id)
        return {
            "job_id": job_id,
            "status": res.status,
            "result": res.result if res.ready() else None
        }
    else:
        if job_id not in JOB_STORE:
            raise HTTPException(status_code=404, detail="Job ID not found.")
        return {"job_id": job_id, **JOB_STORE[job_id]}


@router.get("", response_model=List[ForecastResult])
def get_forecast(
    trade_lane_id: int = Query(..., description="Target Trade Lane ID"),
    vessel_class_id: int = Query(..., description="Target Vessel Class ID"),
    horizons: List[int] = Query([7, 30, 90, 180], description="Forecast horizons in days"),
    target_variable: str = Query("TCE_rate", description="Target variable (TCE_rate or spot_rate)"),
    db: Session = Depends(get_db)
) -> List[ForecastResult]:
    """
    Gets rate forecast predictions for specified trade lane, vessel class, and horizons.
    Uses active model champion if available, else gracefully degrades to naive seasonal baseline.
    """
    service = ForecastingService(db)
    return service.get_forecast(
        trade_lane_id=trade_lane_id,
        vessel_class_id=vessel_class_id,
        horizons=horizons,
        target_variable=target_variable
    )


@router.get("/audit")
def get_model_audit_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns an audit summary of model coverage across all trade lanes & vessel classes,
    training row counts, active champions, and walk-forward validation metrics.
    """
    from app.forecasting.audit import audit_model_coverage_and_quality
    return audit_model_coverage_and_quality(db)


@router.get("/models", response_model=List[ModelRegistryResponse])
def list_models(
    trade_lane_id: Optional[int] = Query(None),
    vessel_class_id: Optional[int] = Query(None),
    active_only: bool = Query(False),
    db: Session = Depends(get_db)
) -> List[ModelRegistryResponse]:
    """
    Lists registered forecaster models and their backtest evaluation metrics.
    """
    query = db.query(ModelRegistry)
    if trade_lane_id is not None:
        query = query.filter(ModelRegistry.target_trade_lane_id == trade_lane_id)
    if vessel_class_id is not None:
        query = query.filter(ModelRegistry.target_vessel_class_id == vessel_class_id)
    if active_only:
        query = query.filter(ModelRegistry.is_active == True)

    return query.order_by(ModelRegistry.created_at.desc()).all()
