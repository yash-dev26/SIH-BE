"""Pydantic request/response contracts for recommendations. The
`/recommend` endpoint (Phase 5) accepts a RecommendationRequest and, once the
Optimization Engine (Phase 4) has run, returns a RecommendationRead."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecommendationRequest(BaseModel):
    """Cargo-input form payload — Section 4, Phase 6, task 1."""

    commodity: str
    quantity_mt: float
    candidate_origin_ports: list[int] = Field(..., description="Candidate origin port_ids")
    destination_ports: list[int] = Field(..., description="Candidate ECI destination port_ids")
    laycan_start: date
    laycan_end: date
    contract_type_preference: (
        Literal["SPOT", "SHORT_TERM", "MEDIUM_TERM", "COA", "PERIOD", "LET_SYSTEM_DECIDE"]
    ) = "LET_SYSTEM_DECIDE"
    risk_tolerance: Literal["conservative", "neutral", "aggressive"] = "neutral"


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: uuid.UUID
    request_payload: dict
    recommended_vessel_class_id: int | None
    recommended_contract_type: str | None
    recommended_entry_window_start: date | None
    recommended_entry_window_end: date | None
    expected_cost_usd: float | None
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    rationale_json: dict | None
    risk_flags: dict | None
    created_at: datetime
