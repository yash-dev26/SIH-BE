from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.optimization.recommendation_service import RecommendationService
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse

router = APIRouter(prefix="/recommend", tags=["Recommendation & Optimization Engine"])


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
