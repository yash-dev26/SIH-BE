from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import TradeLane, VesselClass
from app.deps import get_db
from app.forecasting.inference_service import ForecastingService
from app.optimization.scenario_simulator import compare_charter_scenarios
from app.schemas.recommendation import ScenarioCompareRequest, ScenarioCompareResponse

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


@router.post("/compare", response_model=ScenarioCompareResponse)
def compare_scenarios(
    request: ScenarioCompareRequest,
    db: Session = Depends(get_db),
) -> ScenarioCompareResponse:
    """
    Standalone Spot vs COA vs Period cost comparison for a given trade lane / vessel class /
    cargo quantity, independent of the full /recommend flow - lets the frontend's
    ScenarioCompare.tsx re-run "what if" comparisons (e.g. a different quantity) without
    re-solving origin/vessel selection each time.
    """
    lane = db.query(TradeLane).filter(TradeLane.trade_lane_id == request.trade_lane_id).first()
    if not lane:
        raise HTTPException(status_code=404, detail=f"Trade lane {request.trade_lane_id} not found.")
    vclass = db.query(VesselClass).filter(VesselClass.vessel_class_id == request.vessel_class_id).first()
    if not vclass:
        raise HTTPException(status_code=404, detail=f"Vessel class {request.vessel_class_id} not found.")

    forecasting_svc = ForecastingService(db)
    fc_results = forecasting_svc.get_forecast(
        trade_lane_id=request.trade_lane_id,
        vessel_class_id=request.vessel_class_id,
        horizons=[30],
    )
    if not fc_results:
        raise HTTPException(status_code=500, detail="Forecast unavailable for this lane/class.")
    fc = fc_results[0]

    usable_capacity_mt = float(vclass.dwt_max) * 0.95
    vessel_utilization_pct = min(100.0, round((request.cargo_qty_mt / usable_capacity_mt) * 100.0, 1))
    transit_days = float(lane.typical_transit_days_laden or (float(lane.sea_distance_nm) / 300.0))

    scenarios, recommended_contract, rationale_msg, winning_scenario = compare_charter_scenarios(
        cargo_qty_mt=request.cargo_qty_mt,
        sea_distance_nm=float(lane.sea_distance_nm),
        transit_days=transit_days,
        tce_rate_usd_day=fc.point_forecast,
        bunker_consumption_tpd=vclass.bunker_consumption_tpd,
        port_dues_usd=vclass.typical_port_dues_usd,
        vessel_utilization_pct=vessel_utilization_pct,
        forecast_p10=fc.p10,
        forecast_p90=fc.p90,
    )

    return ScenarioCompareResponse(
        trade_lane_id=request.trade_lane_id,
        vessel_class_id=request.vessel_class_id,
        cargo_qty_mt=request.cargo_qty_mt,
        vessel_utilization_pct=vessel_utilization_pct,
        forecasted_tce_rate_usd_day=fc.point_forecast,
        forecast_p10=fc.p10,
        forecast_p90=fc.p90,
        model_fallback_used=fc.model_fallback_used,
        scenarios=scenarios,
        recommended_contract_type=recommended_contract,
        rationale=rationale_msg,
    )
