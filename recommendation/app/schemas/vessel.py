from typing import Optional

from pydantic import BaseModel, ConfigDict


class VesselClassResponse(BaseModel):
    vessel_class_id: int
    class_name: str
    dwt_min: int
    dwt_max: int
    typical_loa_m: Optional[float] = None
    typical_beam_m: Optional[float] = None
    typical_laden_draft_m: Optional[float] = None
    bunker_consumption_tpd: float
    typical_port_dues_usd: float

    model_config = ConfigDict(from_attributes=True)


class TradeLaneResponse(BaseModel):
    trade_lane_id: int
    origin_port_code: str
    destination_port_code: str
    vessel_class_id: Optional[int] = None
    sea_distance_nm: float
    typical_transit_days_laden: Optional[float] = None
    commodity: str

    model_config = ConfigDict(from_attributes=True)
