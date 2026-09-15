from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CharterContractCreate(BaseModel):
    recommendation_id: Optional[str] = Field(None, description="Optional linked recommendations.recommendation_id")
    contract_type: str = Field(..., description="SPOT, COA, or PERIOD")
    commodity: Optional[str] = None
    cargo_qty_mt: Optional[float] = Field(None, gt=0)
    origin_port_code: Optional[str] = None
    destination_port_code: Optional[str] = None
    trade_lane_id: Optional[int] = None
    vessel_class_id: Optional[int] = None
    tce_rate_usd_day: Optional[float] = None
    total_cost_usd: Optional[float] = None
    laytime_allowed_days: Optional[float] = Field(
        None, description="Nullable - defaults to settings.DEFAULT_LAYTIME_ALLOWED_DAYS when not negotiated"
    )
    demurrage_rate_usd_per_day: Optional[float] = Field(
        None, description="Nullable - defaults to settings.DEFAULT_DEMURRAGE_RATE_USD_PER_DAY when not negotiated"
    )
    entry_window_start: Optional[date] = None
    entry_window_end: Optional[date] = None
    status: str = Field("DRAFT", description="DRAFT, CONFIRMED, or CANCELLED")


class CharterContractUpdate(BaseModel):
    contract_type: Optional[str] = None
    cargo_qty_mt: Optional[float] = Field(None, gt=0)
    tce_rate_usd_day: Optional[float] = None
    total_cost_usd: Optional[float] = None
    laytime_allowed_days: Optional[float] = None
    demurrage_rate_usd_per_day: Optional[float] = None
    entry_window_start: Optional[date] = None
    entry_window_end: Optional[date] = None
    status: Optional[str] = Field(None, description="DRAFT, CONFIRMED, or CANCELLED")


class CharterContractResponse(BaseModel):
    contract_id: str
    recommendation_id: Optional[str] = None
    contract_type: str
    commodity: Optional[str] = None
    cargo_qty_mt: Optional[float] = None
    origin_port_code: Optional[str] = None
    destination_port_code: Optional[str] = None
    trade_lane_id: Optional[int] = None
    vessel_class_id: Optional[int] = None
    tce_rate_usd_day: Optional[float] = None
    total_cost_usd: Optional[float] = None
    laytime_allowed_days: float
    demurrage_rate_usd_per_day: float
    entry_window_start: Optional[date] = None
    entry_window_end: Optional[date] = None
    status: str
    created_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
