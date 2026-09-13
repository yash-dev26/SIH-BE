"""Pydantic request/response contracts for charter contracts."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RateUnit = Literal["USD_PER_MT", "USD_PER_DAY"]


class CharterContractBase(BaseModel):
    contract_type: Literal["SPOT", "SHORT_TERM", "MEDIUM_TERM", "COA", "PERIOD"]
    vessel_id: int | None = Field(default=None, description="Nullable for COA (vessel TBN)")
    vessel_class_id: int
    trade_lane_id: int
    commodity_id: int
    cargo_qty_mt: float
    laycan_start: date
    laycan_end: date
    fixed_rate_value: float | None = None
    fixed_rate_unit: RateUnit | None = None
    num_voyages: int = 1
    status: Literal["PROPOSED", "FIXED", "LAYCAN_ACTIVE", "COMPLETED", "CANCELLED"] = "PROPOSED"

    @model_validator(mode="after")
    def _rate_value_and_unit_together(self) -> "CharterContractBase":
        # Guards the "never an ambiguous rate column" principle: a rate value
        # without its unit (or vice versa) is a broken record, not partial data.
        if (self.fixed_rate_value is None) != (self.fixed_rate_unit is None):
            raise ValueError("fixed_rate_value and fixed_rate_unit must both be set or both be None")
        if self.laycan_end < self.laycan_start:
            raise ValueError("laycan_end must not be before laycan_start")
        return self


class CharterContractCreate(CharterContractBase):
    pass


class CharterContractRead(CharterContractBase):
    model_config = ConfigDict(from_attributes=True)

    contract_id: uuid.UUID
    created_at: datetime
