from datetime import date
from typing import Any, Dict, List, Optional
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from app.forecasting.base_forecaster import BaseForecaster
from app.schemas.forecast import ForecastResult


class LightGBMQuantileForecaster(BaseForecaster):
    """
    Tier 0 Primary Forecaster — Quantile LightGBM Regression.
    Trains 3 separate quantile models (p10, p50 point, p90) over pooled trade lane panel data.
    """

    FEATURE_COLS = [
        "trade_lane_id",
        "vessel_class_id",
        "month",
        "week_of_year",
        "sin_month",
        "cos_month",
        "monsoon_season_flag",
        "cyclone_season_flag",
        "vlsfo_price",
        "vlsfo_price_30d_trend",
        "thermal_coal_price",
        "coking_coal_price",
        "iron_ore_price",
        "avg_waiting_days_load",
        "avg_waiting_days_discharge",
        "sea_distance_nm",
        "typical_transit_days",
        "rate_lag_1d",
        "rate_lag_7d",
        "rate_lag_30d",
        "rate_lag_90d",
        "rate_rolling_mean_7d",
        "rate_rolling_std_7d",
        "rate_rolling_mean_30d",
        "rate_rolling_std_30d",
    ]

    def __init__(self, target_variable: str = "TCE_rate", rate_unit: str = "USD_PER_DAY"):
        super().__init__(model_name="lightgbm_quantile", target_variable=target_variable, rate_unit=rate_unit)
        self.models: Dict[str, lgb.LGBMRegressor] = {}
        self.feature_columns = self.FEATURE_COLS

    def fit(self, panel_df: pd.DataFrame, trade_lane_id: Optional[int] = None, vessel_class_id: Optional[int] = None) -> None:
        df = panel_df.copy()
        if trade_lane_id is not None:
            df = df[df["trade_lane_id"] == trade_lane_id]
        if vessel_class_id is not None:
            df = df[df["vessel_class_id"] == vessel_class_id]

        df = df.dropna(subset=[self.target_variable] + self.feature_columns)

        X = df[self.feature_columns]
        y = df[self.target_variable]

        # Categorical features
        cat_features = ["trade_lane_id", "vessel_class_id"]
        for cat in cat_features:
            X[cat] = X[cat].astype("category")

        # Fit models for p10, p50 (point estimate), p90
        quantiles = {"p10": 0.10, "p50": 0.50, "p90": 0.90}

        for q_name, q_val in quantiles.items():
            params = {
                "objective": "quantile",
                "alpha": q_val,
                "metric": "quantile",
                "n_estimators": 100,
                "learning_rate": 0.05,
                "num_leaves": 31,
                "random_state": 42,
                "verbose": -1,
            }
            model = lgb.LGBMRegressor(**params)
            model.fit(X, y)
            self.models[q_name] = model

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
            raise ValueError("LightGBM model is not fitted yet.")

        # Filter panel for specific lane and class
        df_sub = panel_df[(panel_df["trade_lane_id"] == trade_lane_id) & (panel_df["vessel_class_id"] == vessel_class_id)]
        if df_sub.empty:
            raise ValueError(f"No feature data found for trade_lane_id={trade_lane_id}, vessel_class_id={vessel_class_id}")

        # Get latest feature row
        latest_row = df_sub.sort_values("date").iloc[-1]
        X_pred = pd.DataFrame([latest_row[self.feature_columns]])
        for cat in ["trade_lane_id", "vessel_class_id"]:
            X_pred[cat] = X_pred[cat].astype("category")

        p10 = float(self.models["p10"].predict(X_pred)[0])
        p50 = float(self.models["p50"].predict(X_pred)[0])
        p90 = float(self.models["p90"].predict(X_pred)[0])

        # Adjust for horizon drift factor (uncertainty widens with horizon)
        horizon_factor = 1.0 + (horizon_days / 365.0) * 0.1
        p10 = max(0.0, p50 - (p50 - p10) * horizon_factor)
        p90 = p50 + (p90 - p50) * horizon_factor

        feature_snap = {k: float(v) if isinstance(v, (np.floating, float, int)) else str(v) for k, v in latest_row[self.feature_columns].to_dict().items()}

        return ForecastResult(
            point_forecast=round(p50, 2),
            p10=round(p10, 2),
            p90=round(p90, 2),
            rate_unit=self.rate_unit,
            target_date=target_date,
            horizon_days=horizon_days,
            trade_lane_id=trade_lane_id,
            vessel_class_id=vessel_class_id,
            model_version=self.version,
            feature_snapshot=feature_snap,
        )

    def save(self, filepath: str) -> None:
        state = {
            "models": self.models,
            "version": self.version,
            "target_variable": self.target_variable,
            "rate_unit": self.rate_unit,
            "is_fitted": self.is_fitted,
        }
        joblib.dump(state, filepath)

    @classmethod
    def load(cls, filepath: str) -> "LightGBMQuantileForecaster":
        state = joblib.load(filepath)
        instance = cls(target_variable=state["target_variable"], rate_unit=state["rate_unit"])
        instance.models = state["models"]
        instance.version = state.get("version", "1.0.0")
        instance.is_fitted = state["is_fitted"]
        return instance
