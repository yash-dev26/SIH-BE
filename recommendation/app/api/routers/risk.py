from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import Port, TradeLane, VesselClass
from app.deps import get_db
from app.forecasting.inference_service import ForecastingService
from app.optimization.risk_engine import evaluate_risk_flags

router = APIRouter(prefix="/risk", tags=["Risk"])


@router.get("/{lane_id}")
def get_lane_risk(
    lane_id: int,
    vessel_class_id: Optional[int] = Query(None, description="Defaults to the lane's own vessel_class_id if set"),
    laycan_start: Optional[date] = Query(None, description="Defaults to today"),
    avg_waiting_days_load: float = Query(2.0, description="Empirical port_congestion average at the origin"),
    avg_waiting_days_disch: float = Query(3.5, description="Empirical port_congestion average at the destination"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Section 3.4 early-warning risk engine, surfaced per trade lane. Pulls a live 30-day
    forecast for volatility/uncertainty flags and the origin/destination ports' physical
    draft data for the tide-adjusted draft-margin flag, then runs the same multi-factor
    rule engine the recommendation flow uses - so a risk banner shown ahead of submitting a
    cargo request matches what /recommend would ultimately flag.
    """
    lane = db.query(TradeLane).filter(TradeLane.trade_lane_id == lane_id).first()
    if not lane:
        raise HTTPException(status_code=404, detail=f"Trade lane {lane_id} not found.")

    resolved_vessel_class_id = vessel_class_id or lane.vessel_class_id
    if resolved_vessel_class_id is None:
        raise HTTPException(
            status_code=400,
            detail="This trade lane has no default vessel_class_id - pass ?vessel_class_id=",
        )
    vclass = db.query(VesselClass).filter(VesselClass.vessel_class_id == resolved_vessel_class_id).first()
    if not vclass:
        raise HTTPException(status_code=404, detail=f"Vessel class {resolved_vessel_class_id} not found.")

    origin_port = db.query(Port).filter(Port.port_code == lane.origin_port_code).first()
    dest_port = db.query(Port).filter(Port.port_code == lane.destination_port_code).first()
    if not dest_port:
        raise HTTPException(status_code=404, detail=f"Destination port '{lane.destination_port_code}' not found.")

    effective_laycan_start = laycan_start or date.today()

    forecasting_svc = ForecastingService(db)
    fc_results = forecasting_svc.get_forecast(
        trade_lane_id=lane_id,
        vessel_class_id=resolved_vessel_class_id,
        horizons=[30],
    )
    fc = fc_results[0] if fc_results else None

    flags = evaluate_risk_flags(
        origin_port_code=lane.origin_port_code,
        origin_port_name=origin_port.port_name if origin_port else lane.origin_port_code,
        destination_port_code=lane.destination_port_code,
        destination_port_name=dest_port.port_name,
        vessel_class_name=vclass.class_name,
        vessel_laden_draft_m=float(vclass.typical_laden_draft_m or 13.5),
        dest_charted_draft_m=float(dest_port.max_draft_charted_m or 16.5),
        dest_tide_m=float(dest_port.tidal_range_m or 2.0),
        forecast_point=fc.point_forecast if fc else 15000.0,
        forecast_p10=fc.p10 if fc and fc.p10 is not None else 12000.0,
        forecast_p90=fc.p90 if fc and fc.p90 is not None else 18000.0,
        laycan_start=effective_laycan_start,
        sea_distance_nm=float(lane.sea_distance_nm),
        avg_waiting_days_load=avg_waiting_days_load,
        avg_waiting_days_disch=avg_waiting_days_disch,
    )

    return {
        "trade_lane_id": lane_id,
        "vessel_class_id": resolved_vessel_class_id,
        "origin_port_code": lane.origin_port_code,
        "destination_port_code": lane.destination_port_code,
        "laycan_start": effective_laycan_start.isoformat(),
        "forecasted_tce_rate_usd_day": fc.point_forecast if fc else None,
        "model_fallback_used": fc.model_fallback_used if fc else True,
        "risk_flags": flags,
    }
