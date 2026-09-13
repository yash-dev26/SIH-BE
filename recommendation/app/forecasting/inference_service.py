from datetime import date, timedelta
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session

from app.db.models import Forecast
from app.features.build_training_panel import get_training_panel
from app.forecasting.registry import ModelRegistryManager
from app.schemas.forecast import ForecastResult


class ForecastingService:
    """
    Inference Service for FreightIQ.
    Serves forecasts using active model champions from registry, persists to DB,
    and falls back to naive seasonal-average baseline if no trained model exists.
    """

    def __init__(self, db: Session):
        self.db = db
        self.registry_mgr = ModelRegistryManager(db)

    def get_forecast(
        self,
        trade_lane_id: int,
        vessel_class_id: int,
        horizons: List[int] = [7, 30, 90, 180],
        as_of_date: Optional[date] = None,
        target_variable: str = "TCE_rate"
    ) -> List[ForecastResult]:
        if as_of_date is None:
            as_of_date = date.today()

        panel_df = get_training_panel(as_of_date=as_of_date, lanes=[trade_lane_id], classes=[vessel_class_id])

        # 1. Fetch active champion model via hierarchical lookup
        forecaster, model_meta, lookup_reason = self.registry_mgr.get_active_model(
            trade_lane_id=trade_lane_id,
            vessel_class_id=vessel_class_id,
            target_variable=target_variable
        )

        num_rows = len(panel_df[(panel_df["trade_lane_id"] == trade_lane_id) & (panel_df["vessel_class_id"] == vessel_class_id)])
        if num_rows == 0:
            num_rows = len(panel_df)

        results: List[ForecastResult] = []

        for horizon in horizons:
            target_d = as_of_date + timedelta(days=horizon)

            if forecaster is not None and model_meta is not None:
                try:
                    res = forecaster.predict(
                        panel_df=panel_df,
                        trade_lane_id=trade_lane_id,
                        vessel_class_id=vessel_class_id,
                        target_date=target_d,
                        horizon_days=horizon
                    )
                    res.model_id = model_meta.model_id
                    res.model_version = model_meta.version
                    res.model_fallback_used = False
                    res.model_fallback_reason = lookup_reason
                    res.model_training_rows = (model_meta.metrics_json or {}).get("num_samples", num_rows)
                except Exception as e:
                    res = self._fallback_naive_forecast(panel_df, trade_lane_id, vessel_class_id, target_d, horizon, target_variable, f"Inference execution failed ({e})")
            else:
                # Graceful degradation fallback
                res = self._fallback_naive_forecast(panel_df, trade_lane_id, vessel_class_id, target_d, horizon, target_variable, lookup_reason)

            # Persist forecast to DB
            self._persist_forecast(res, model_meta.model_id if model_meta else "NAIVE_FALLBACK")
            results.append(res)

        return results

    def _fallback_naive_forecast(
        self,
        panel_df: Any,
        trade_lane_id: int,
        vessel_class_id: int,
        target_date: date,
        horizon_days: int,
        target_variable: str,
        fallback_reason: str = "No active model champion found"
    ) -> ForecastResult:
        """
        Graceful degradation: Naive seasonal rolling average baseline.
        Used when no active model champion is available.
        """
        df_sub = panel_df[(panel_df["trade_lane_id"] == trade_lane_id) & (panel_df["vessel_class_id"] == vessel_class_id)]
        num_rows = len(df_sub)
        if not df_sub.empty:
            recent_rates = df_sub[target_variable].dropna().tail(30)
            mean_rate = float(recent_rates.mean()) if not recent_rates.empty else 15000.0
            std_rate = float(recent_rates.std()) if len(recent_rates) > 1 else 2000.0
            latest_row = df_sub.sort_values("date").iloc[-1]
            snap = {k: float(v) if isinstance(v, (np.floating, float, int)) else str(v) for k, v in latest_row.to_dict().items() if k in ["vlsfo_price", "TCE_rate"]}
        else:
            mean_rate = 15000.0
            std_rate = 2500.0
            snap = {}

        return ForecastResult(
            point_forecast=round(mean_rate, 2),
            p10=round(max(0.0, mean_rate - 1.28 * std_rate), 2),
            p90=round(mean_rate + 1.28 * std_rate, 2),
            rate_unit="USD_PER_DAY" if target_variable == "TCE_rate" else "USD_PER_MT",
            target_date=target_date,
            horizon_days=horizon_days,
            trade_lane_id=trade_lane_id,
            vessel_class_id=vessel_class_id,
            model_version="0.0.0_naive_fallback",
            model_id="NAIVE_FALLBACK",
            model_fallback_used=True,
            model_fallback_reason=fallback_reason,
            model_training_rows=num_rows,
            feature_snapshot=snap,
        )

    def _persist_forecast(self, res: ForecastResult, model_id: str) -> None:
        try:
            fc_db = Forecast(
                model_id=model_id,
                trade_lane_id=res.trade_lane_id,
                vessel_class_id=res.vessel_class_id,
                target_date=res.target_date,
                horizon_days=res.horizon_days,
                predicted_rate=res.point_forecast,
                predicted_rate_p10=res.p10,
                predicted_rate_p90=res.p90,
                rate_unit=res.rate_unit,
                feature_snapshot=res.feature_snapshot
            )
            self.db.add(fc_db)
            self.db.commit()
        except Exception:
            self.db.rollback()


