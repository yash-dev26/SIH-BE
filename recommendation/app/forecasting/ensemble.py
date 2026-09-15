from datetime import date
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from app.forecasting.base_forecaster import BaseForecaster
from app.schemas.forecast import ForecastResult


class EnsembleForecaster(BaseForecaster):
    """
    Ensemble Forecaster — Combines multiple fitted base forecasters (LightGBM, Prophet, SARIMAX)
    via weighted averaging for point and prediction interval bounds.
    """

    def __init__(
        self,
        forecasters: List[BaseForecaster],
        weights: Optional[List[float]] = None,
        target_variable: str = "TCE_rate",
        rate_unit: str = "USD_PER_DAY"
    ):
        super().__init__(model_name="ensemble", target_variable=target_variable, rate_unit=rate_unit)
        self.forecasters = forecasters
        if weights is None:
            weights = [1.0 / len(forecasters)] * len(forecasters)
        else:
            total = sum(weights)
            weights = [w / total for w in weights]
        self.weights = weights
        self.is_fitted = all(f.is_fitted for f in self.forecasters)

    def fit(self, panel_df: pd.DataFrame, trade_lane_id: Optional[int] = None, vessel_class_id: Optional[int] = None) -> None:
        for f in self.forecasters:
            f.fit(panel_df, trade_lane_id=trade_lane_id, vessel_class_id=vessel_class_id)
        self.is_fitted = True

    def predict(
        self,
        panel_df: pd.DataFrame,
        trade_lane_id: int,
        vessel_class_id: int,
        target_date: date,
        horizon_days: int
    ) -> ForecastResult:
        if not self.is_fitted:
            raise ValueError("Not all ensemble component models are fitted.")

        results: List[ForecastResult] = [
            f.predict(panel_df, trade_lane_id, vessel_class_id, target_date, horizon_days)
            for f in self.forecasters
        ]

        points = [r.point_forecast for r in results]
        p10s = [r.p10 if r.p10 is not None else r.point_forecast for r in results]
        p90s = [r.p90 if r.p90 is not None else r.point_forecast for r in results]

        avg_point = sum(w * p for w, p in zip(self.weights, points))
        avg_p10 = sum(w * p for w, p in zip(self.weights, p10s))
        avg_p90 = sum(w * p for w, p in zip(self.weights, p90s))

        merged_snapshot = {}
        for r in results:
            if r.feature_snapshot:
                merged_snapshot.update(r.feature_snapshot)

        return ForecastResult(
            point_forecast=round(avg_point, 2),
            p10=round(avg_p10, 2),
            p90=round(avg_p90, 2),
            rate_unit=self.rate_unit,
            target_date=target_date,
            horizon_days=horizon_days,
            trade_lane_id=trade_lane_id,
            vessel_class_id=vessel_class_id,
            model_version=self.version,
            feature_snapshot=merged_snapshot,
        )

    def save(self, filepath: str) -> None:
        pass

    @classmethod
    def load(cls, filepath: str) -> "EnsembleForecaster":
        raise NotImplementedError("Ensemble loading handled via component model registry loading.")


