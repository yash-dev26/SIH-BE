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
    risk_tolerance: Optional[str] = Field("balanced", description="Risk tolerance (low, balanced, high)")



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
