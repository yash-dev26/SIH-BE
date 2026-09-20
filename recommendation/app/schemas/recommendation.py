from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class RecommendationRequest(BaseModel):
    commodity: str = Field("coking_coal", description="Commodity name (e.g. coking_coal, thermal_coal)")
    cargo_qty_mt: float = Field(
        ...,
        validation_alias=AliasChoices("cargo_qty_mt", "cargo_quantity_mt"),
        description="Cargo quantity in Metric Tons (e.g. 75000)"
    )
    destination_port_code: str = Field("INPRT", description="Destination port UNLOCODE (e.g. INPRT for Paradip Port)")
    laycan_start: date = Field(..., description="Laycan window start date")
    laycan_end: date = Field(..., description="Laycan window end date")
    risk_tolerance: Optional[str] = Field("balanced", validation_alias=AliasChoices("risk_tolerance", "riskTolerance"), description="Risk tolerance (low, balanced, high)")
    contract_preference: Optional[str] = Field(
        "let_system_decide",
        validation_alias=AliasChoices("contract_preference", "contractPreference"),
        description="Contract selection preference: let_system_decide, spot, short_term, coa, period"
    )


class RecommendationResponse(BaseModel):
    status: str = "SUCCESS"
    message: Optional[str] = None
    commodity: Optional[str] = None
    cargo_qty_mt: Optional[float] = None
    destination_port_code: Optional[str] = None
    recommended_origin_port: Optional[str] = None
    recommended_origin_port_code: Optional[str] = None
    recommended_vessel_class: Optional[str] = None
    recommended_trade_lane_id: Optional[int] = None
    recommended_contract_type: Optional[str] = None
    recommended_entry_window_start: Optional[str] = None
    recommended_entry_window_end: Optional[str] = None
    expected_total_cost_usd: Optional[float] = None
    cost_per_mt_usd: Optional[float] = None
    forecasted_tce_rate_usd_day: Optional[float] = None
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    model_fallback_used: Optional[bool] = None
    model_fallback_reason: Optional[str] = None
    model_training_rows: Optional[int] = None
    vessel_utilization_pct: Optional[float] = None
    candidates_considered_count: Optional[int] = None
    feasible_candidates_count: Optional[int] = 0
    cost_breakdown: Optional[Dict[str, Any]] = None
    rejected_candidates: Optional[List[Dict[str, Any]]] = None
    rationale: Optional[Dict[str, Any]] = None
    risk_flags: Optional[List[Dict[str, Any]]] = None
    charter_scenarios: Optional[List[Dict[str, Any]]] = None

    # New structured fields
    destination: Optional[Dict[str, Any]] = None
    origin: Optional[Dict[str, Any]] = None
    vessel: Optional[Dict[str, Any]] = None
    contract: Optional[Dict[str, Any]] = None
    entry_window: Optional[Dict[str, Any]] = None
    forecast: Optional[Dict[str, Any]] = None
    why_selected: Optional[List[str]] = None
    alternatives: Optional[List[Dict[str, Any]]] = None
    voyage_weather: Optional[Dict[str, Any]] = None
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





