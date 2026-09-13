"""Pydantic request/response contracts for forecasts. The Forecasting Engine
(Phase 3) will produce these; the API (Phase 5) serves them."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RateUnit = Literal["USD_PER_MT", "USD_PER_DAY"]


class ForecastBase(BaseModel):
    model_id: uuid.UUID
    trade_lane_id: int
    vessel_class_id: int
    target_date: date
    horizon_days: int = Field(..., description="7, 30, 90, or 180 per Section 3.1")
    predicted_rate: float
    predicted_rate_p10: float | None = Field(default=None, description="Lower bound of the prediction interval")
    predicted_rate_p90: float | None = Field(default=None, description="Upper bound of the prediction interval")
    rate_unit: RateUnit
    feature_snapshot: dict | None = Field(
        default=None, description="Exact features used at prediction time, for auditability"
    )

    @model_validator(mode="after")
    def _p10_le_point_le_p90(self) -> "ForecastBase":
        if self.predicted_rate_p10 is not None and self.predicted_rate_p10 > self.predicted_rate:
            raise ValueError("predicted_rate_p10 must not exceed predicted_rate")
        if self.predicted_rate_p90 is not None and self.predicted_rate_p90 < self.predicted_rate:
            raise ValueError("predicted_rate_p90 must not be below predicted_rate")
        return self


class ForecastCreate(ForecastBase):
    pass


class ForecastRead(ForecastBase):
    model_config = ConfigDict(from_attributes=True)

    forecast_id: uuid.UUID
    forecast_made_at: datetime
