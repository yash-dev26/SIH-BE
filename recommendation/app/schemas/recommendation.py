from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RecommendationRequest(BaseModel):
    commodity: str = Field("coking_coal", description="Commodity name (e.g. coking_coal, thermal_coal)")
    cargo_qty_mt: float = Field(..., description="Cargo quantity in Metric Tons (e.g. 75000)")
    destination_port_code: str = Field("INPRT", description="Destination port UNLOCODE (e.g. INPRT for Paradip Port)")
    laycan_start: date = Field(..., description="Laycan window start date")
    laycan_end: date = Field(..., description="Laycan window end date")


class RecommendationResponse(BaseModel):
    commodity: str
    cargo_qty_mt: float
    destination_port_code: str
    recommended_origin_port: str
    recommended_origin_port_code: str
    recommended_vessel_class: str
    recommended_trade_lane_id: int
    recommended_contract_type: str
    recommended_entry_window_start: str
    recommended_entry_window_end: str
    expected_total_cost_usd: float
    cost_per_mt_usd: float
    forecasted_tce_rate_usd_day: float
    model_id: str
    model_version: str
    model_fallback_used: bool
    model_fallback_reason: Optional[str] = None
    model_training_rows: int
    vessel_utilization_pct: float
    candidates_considered_count: int
    feasible_candidates_count: int
    cost_breakdown: Dict[str, Any]
    rejected_candidates: List[Dict[str, Any]]
    rationale: Dict[str, Any]
    risk_flags: List[Dict[str, Any]]
    charter_scenarios: List[Dict[str, Any]]

    # New structured fields
    destination: Optional[Dict[str, Any]] = None
    origin: Optional[Dict[str, Any]] = None
    vessel: Optional[Dict[str, Any]] = None
    contract: Optional[Dict[str, Any]] = None
    entry_window: Optional[Dict[str, Any]] = None
    forecast: Optional[Dict[str, Any]] = None
    why_selected: Optional[List[str]] = None
    alternatives: Optional[List[Dict[str, Any]]] = None
    human_readable_summary: Optional[str] = None

    model_config = ConfigDict(extra="ignore", from_attributes=True)


class CargoParcelRequest(BaseModel):
    parcel_id: str = Field(..., description="Caller-assigned unique identifier for this cargo parcel")
    commodity: str = Field("coking_coal", description="Commodity name (e.g. coking_coal, thermal_coal)")
    cargo_qty_mt: float = Field(..., description="Cargo quantity in Metric Tons")
    destination_port_code: str = Field("INPRT", description="Destination port UNLOCODE")
    laycan_start: date = Field(..., description="Laycan window start date")
    laycan_end: date = Field(..., description="Laycan window end date")


class BatchRecommendationRequest(BaseModel):
    parcels: List[CargoParcelRequest] = Field(..., description="Cargo parcels to jointly optimize")
    spot_cap_ratio: float = Field(
        0.4, ge=0.0, le=1.0,
        description="Max share of total cargo volume allowed on SPOT contracts (Section 3.2, constraint 9)"
    )
    full_optimization: bool = Field(
        False,
        description="Force the async full CP-SAT multi-parcel solve even for small parcel books"
    )


class IdleOpportunity(BaseModel):
    opportunity_id: str
    cargo_qty_mt: float
    origin_port_code: str
    destination_port_code: str
    ballast_distance_nm: float = 0.0
    transit_days: float = 10.0
    tce_rate_usd_day: float = 15000.0
    laycan_start_in_days: float = 0.0
    is_backhaul: bool = False


class IdleMitigationRequest(BaseModel):
    vessel_class_name: str
    idle_position_port_code: str
    idle_days_available: float
    bunker_consumption_tpd: float = 25.0
    open_opportunities: List[IdleOpportunity]
    top_n: int = 3


class ScenarioCompareRequest(BaseModel):
    trade_lane_id: int = Field(..., description="Trade lane ID to price scenarios for")
    vessel_class_id: int = Field(..., description="Vessel class ID to price scenarios for")
    cargo_qty_mt: float = Field(..., gt=0, description="Cargo quantity in Metric Tons")


class ScenarioCompareResponse(BaseModel):
    trade_lane_id: int
    vessel_class_id: int
    cargo_qty_mt: float
    vessel_utilization_pct: float
    forecasted_tce_rate_usd_day: float
    forecast_p10: Optional[float] = None
    forecast_p90: Optional[float] = None
    model_fallback_used: bool
    scenarios: List[Dict[str, Any]]
    recommended_contract_type: str
    rationale: str





