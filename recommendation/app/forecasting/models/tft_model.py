from datetime import date
from typing import Optional
import pandas as pd

from app.forecasting.base_forecaster import BaseForecaster
from app.schemas.forecast import ForecastResult


class TemporalFusionTransformerForecaster(BaseForecaster):
    """
    Tier 1 (v2 Upgrade Path) — Temporal Fusion Transformer (TFT).
    Multi-horizon, multi-entity transformer for time-series forecasting.
    """

    def __init__(self, target_variable: str = "TCE_rate", rate_unit: str = "USD_PER_DAY"):
        super().__init__(model_name="tft", target_variable=target_variable, rate_unit=rate_unit)

    def fit(self, panel_df: pd.DataFrame, trade_lane_id: Optional[int] = None, vessel_class_id: Optional[int] = None) -> None:
        raise NotImplementedError("TFT model is a Tier 1 (v2) upgrade component behind BaseForecaster interface.")

    def predict(
        self,
        panel_df: pd.DataFrame,
        trade_lane_id: int,
        vessel_class_id: int,
        target_date: date,
        horizon_days: int
    ) -> ForecastResult:
        raise NotImplementedError("TFT model is a Tier 1 (v2) upgrade component behind BaseForecaster interface.")

    def save(self, filepath: str) -> None:
        pass

    @classmethod
    def load(cls, filepath: str) -> "TemporalFusionTransformerForecaster":
        return cls()
