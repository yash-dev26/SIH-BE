from datetime import date, timedelta
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd

from app.forecasting.base_forecaster import BaseForecaster
from app.schemas.forecast import ModelMetricsSchema


class WalkForwardBacktester:
    """
    Walk-Forward (Expanding Window) Backtest Harness for FreightIQ Forecasters.
    Evaluates RMSE, MAPE, Directional Accuracy, and Pinball Loss without time-series data leakage.
    """

    def __init__(self, min_train_days: int = 365, step_days: int = 30, horizons: List[int] = [7, 30, 90, 180]):
        self.min_train_days = min_train_days
        self.step_days = step_days
        self.horizons = horizons

    def evaluate(
        self,
        forecaster_class: type[BaseForecaster],
        panel_df: pd.DataFrame,
        trade_lane_id: int,
        vessel_class_id: int,
        target_variable: str = "TCE_rate"
    ) -> Dict[str, Any]:
        """
        Executes expanding window walk-forward backtest.
        """
        df_sub = panel_df[
            (panel_df["trade_lane_id"] == trade_lane_id) &
            (panel_df["vessel_class_id"] == vessel_class_id)
        ].sort_values("date").reset_index(drop=True)

        if len(df_sub) < self.min_train_days + max(self.horizons):
            raise ValueError(f"Insufficient history ({len(df_sub)} days) for backtesting.")

        total_days = len(df_sub)
        y_actual_list = []
        y_pred_list = []
        p10_list = []
        p90_list = []
        actual_direction_list = []
        pred_direction_list = []

        for cutoff_idx in range(self.min_train_days, total_days - max(self.horizons), self.step_days):
            train_df = df_sub.iloc[:cutoff_idx].copy()
            cutoff_date = train_df["date"].iloc[-1].date() if isinstance(train_df["date"].iloc[-1], pd.Timestamp) else train_df["date"].iloc[-1]

            forecaster = forecaster_class(target_variable=target_variable)
            try:
                forecaster.fit(train_df, trade_lane_id=trade_lane_id, vessel_class_id=vessel_class_id)
            except Exception:
                continue

            # Predict across test horizons
            for horizon in self.horizons:
                test_idx = cutoff_idx + horizon - 1
                if test_idx >= total_days:
                    continue

                test_row = df_sub.iloc[test_idx]
                target_d = test_row["date"].date() if isinstance(test_row["date"], pd.Timestamp) else test_row["date"]
                actual = float(test_row[target_variable])

                try:
                    res = forecaster.predict(
                        panel_df=df_sub.iloc[:cutoff_idx+1],
                        trade_lane_id=trade_lane_id,
                        vessel_class_id=vessel_class_id,
                        target_date=target_d,
                        horizon_days=horizon
                    )
                    pred = res.point_forecast
                    p10 = res.p10 if res.p10 is not None else pred
                    p90 = res.p90 if res.p90 is not None else pred

                    # Directional calculation compared to cutoff date actual
                    cutoff_actual = float(train_df[target_variable].iloc[-1])
                    actual_dir = np.sign(actual - cutoff_actual)
                    pred_dir = np.sign(pred - cutoff_actual)

                    y_actual_list.append(actual)
                    y_pred_list.append(pred)
                    p10_list.append(p10)
                    p90_list.append(p90)
                    actual_direction_list.append(actual_dir)
                    pred_direction_list.append(pred_dir)
                except Exception:
                    continue

        if not y_actual_list:
            return {"rmse": 9999.0, "mape": 100.0, "directional_accuracy": 0.0, "pinball_loss": 9999.0}

        y_actual = np.array(y_actual_list)
        y_pred = np.array(y_pred_list)

        # RMSE
        rmse = float(np.sqrt(np.mean((y_actual - y_pred) ** 2)))

        # MAPE (%)
        mape = float(np.mean(np.abs((y_actual - y_pred) / np.maximum(1e-5, y_actual))) * 100.0)

        # Directional Accuracy (%)
        dir_acc = float(np.mean(np.array(actual_direction_list) == np.array(pred_direction_list)) * 100.0)

        # Pinball Loss (Quantile Loss at tau=0.1, 0.9)
        p10_loss = np.mean(np.maximum(0.1 * (y_actual - np.array(p10_list)), (0.1 - 1.0) * (y_actual - np.array(p10_list))))
        p90_loss = np.mean(np.maximum(0.9 * (y_actual - np.array(p90_list)), (0.9 - 1.0) * (y_actual - np.array(p90_list))))
        pinball_loss = float((p10_loss + p90_loss) / 2.0)

        return {
            "rmse": round(rmse, 2),
            "mape": round(mape, 2),
            "directional_accuracy": round(dir_acc, 2),
            "pinball_loss": round(pinball_loss, 2),
            "num_samples": len(y_actual_list)
        }


