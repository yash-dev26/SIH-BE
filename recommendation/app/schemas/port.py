from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PortResponse(BaseModel):
    port_id: int
    port_code: str
    port_name: str
    country: str
    role: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    max_loa_m: Optional[float] = None
    max_beam_m: Optional[float] = None
    max_draft_charted_m: Optional[float] = None
    tidal_range_m: Optional[float] = None
    cargo_handling_rate_mt_per_day: Optional[float] = None
    berth_count: Optional[int] = None
    notes: Optional[str] = None
    source: Optional[str] = None
    figures_verified: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class VesselFeasibilityRow(BaseModel):
    vessel_class_id: int
    vessel_class_name: str
    is_feasible: bool
    reasons: List[str] = []


class PortConstraintsResponse(BaseModel):
    port: PortResponse
    tide_allowance_m: float
    vessel_feasibility: List[VesselFeasibilityRow]

    model_config = ConfigDict(from_attributes=True)
