from datetime import date
from typing import Any, Dict, Optional
import joblib
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from app.forecasting.base_forecaster import BaseForecaster
from app.schemas.forecast import ForecastResult


class SARIMAXForecaster(BaseForecaster):
    """
    Tier 0 Alt Forecaster — Statsmodels SARIMAX.
    Models autocorrelation structure + exogenous bunker and commodity variables.
    """

    def __init__(self, target_variable: str = "TCE_rate", rate_unit: str = "USD_PER_DAY"):
        super().__init__(model_name="sarimax", target_variable=target_variable, rate_unit=rate_unit)
        self.model_res = None
        self.exog_cols = ["vlsfo_price", "thermal_coal_price"]

    def fit(self, panel_df: pd.DataFrame, trade_lane_id: Optional[int] = None, vessel_class_id: Optional[int] = None) -> None:
        df = panel_df.copy()
        if trade_lane_id is not None:
            df = df[df["trade_lane_id"] == trade_lane_id]
        if vessel_class_id is not None:
            df = df[df["vessel_class_id"] == vessel_class_id]

        if df.empty:
            raise ValueError(f"Empty data for trade_lane_id={trade_lane_id}, vessel_class_id={vessel_class_id}")

        y = df[self.target_variable].values
        exog = df[self.exog_cols].values

        # Lightweight SARIMAX (1,1,1) x (0,0,0) for fast robust fitting
        model = SARIMAX(y, exog=exog, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False)
        self.model_res = model.fit(disp=False)
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
            raise ValueError("SARIMAX model is not fitted.")

        df_sub = panel_df[(panel_df["trade_lane_id"] == trade_lane_id) & (panel_df["vessel_class_id"] == vessel_class_id)]
        latest_row = df_sub.sort_values("date").iloc[-1] if not df_sub.empty else None

        exog_pred = np.array([[
            latest_row["vlsfo_price"] if latest_row is not None else 550.0,
            latest_row["thermal_coal_price"] if latest_row is not None else 120.0,
        ]])

        forecast_res = self.model_res.get_forecast(steps=horizon_days, exog=np.repeat(exog_pred, horizon_days, axis=0))
        mean_forecast = float(forecast_res.predicted_mean[-1])
        ci = forecast_res.conf_int(alpha=0.20)  # 80% CI ~ p10/p90
        p10 = float(ci[-1, 0])
        p90 = float(ci[-1, 1])

        feature_snap = latest_row.to_dict() if latest_row is not None else {}
        clean_snap = {k: float(v) if isinstance(v, (np.floating, float, int)) else str(v) for k, v in feature_snap.items() if k in ["vlsfo_price", "thermal_coal_price", "TCE_rate"]}

        return ForecastResult(
            point_forecast=round(mean_forecast, 2),
            p10=round(p10, 2),
            p90=round(p90, 2),
            rate_unit=self.rate_unit,
            target_date=target_date,
            horizon_days=horizon_days,
            trade_lane_id=trade_lane_id,
            vessel_class_id=vessel_class_id,
            model_version=self.version,
            feature_snapshot=clean_snap,
        )

    def save(self, filepath: str) -> None:
        joblib.dump({"model_res": self.model_res, "version": self.version, "is_fitted": self.is_fitted}, filepath)

    @classmethod
    def load(cls, filepath: str) -> "SARIMAXForecaster":
        state = joblib.load(filepath)
        inst = cls()
        inst.model_res = state["model_res"]
        inst.version = state.get("version", "1.0.0")
        inst.is_fitted = state["is_fitted"]
        return inst


