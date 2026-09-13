"""Pydantic request/response contracts for vessels and vessel classes."""

from pydantic import BaseModel, ConfigDict, Field


class VesselClassBase(BaseModel):
    class_name: str = Field(..., max_length=50, description="Handysize, Supramax, Panamax, Capesize")
    dwt_min: int
    dwt_max: int
    typical_loa_m: float | None = None
    typical_beam_m: float | None = None
    typical_laden_draft_m: float | None = None


class VesselClassCreate(VesselClassBase):
    pass


class VesselClassRead(VesselClassBase):
    model_config = ConfigDict(from_attributes=True)

    vessel_class_id: int


class VesselBase(BaseModel):
    imo_number: str = Field(..., max_length=15)
    vessel_name: str | None = Field(default=None, max_length=120)
    vessel_class_id: int
    dwt: int
    loa_m: float | None = None
    beam_m: float | None = None
    laden_draft_m: float | None = None
    flag: str | None = Field(default=None, max_length=60)
    build_year: int | None = None


class VesselCreate(VesselBase):
    pass


class VesselRead(VesselBase):
    model_config = ConfigDict(from_attributes=True)

    vessel_id: int
