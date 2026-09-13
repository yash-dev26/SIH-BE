"""Pydantic request/response contracts for ports. Mirrors app/db/models.py::Port
but is the API-facing shape — kept separate from the ORM model per Section 0's
"swappable interface" principle (API contract shouldn't break if the ORM
model's internals change)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PortBase(BaseModel):
    port_code: str = Field(..., max_length=10, description="UNLOCODE preferred, e.g. INPRT")
    port_name: str = Field(..., max_length=120)
    country: str = Field(..., max_length=80)
    role: Literal["LOAD", "DISCHARGE", "BOTH"]
    latitude: float
    longitude: float
    max_loa_m: float | None = None
    max_beam_m: float | None = None
    max_draft_charted_m: float | None = None
    tidal_range_m: float | None = None
    cargo_handling_rate_mt_per_day: float | None = None
    berth_count: int | None = None
    notes: str | None = None


class PortCreate(PortBase):
    pass


class PortRead(PortBase):
    model_config = ConfigDict(from_attributes=True)

    port_id: int
    created_at: datetime
    updated_at: datetime
