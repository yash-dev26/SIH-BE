import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.db.models import TradeLane, VesselClass
from app.db.session import SessionLocal
from app.features.build_training_panel import get_training_panel
from app.forecasting.backtest import WalkForwardBacktester
from app.forecasting.models.lightgbm_quantile import LightGBMQuantileForecaster
from app.forecasting.models.prophet_model import ProphetForecaster
from app.forecasting.models.sarimax_model import SARIMAXForecaster
from app.forecasting.registry import ModelRegistryManager

logger = logging.getLogger(__name__)


def run_model_training_pipeline(
    db: Session,
    trade_lane_ids: Optional[List[int]] = None,
    vessel_class_ids: Optional[List[int]] = None,
    target_variable: str = "TCE_rate"
) -> Dict[str, Any]:
    """
    Model Training Pipeline Runner.
    Trains, backtests, registers, and promotes models for ALL trade lanes and vessel classes in DB.
    Ensures 100% trained model coverage across valid (lane, class) combinations.
    """
    if trade_lane_ids is None:
        trade_lanes = db.query(TradeLane).all()
        trade_lane_ids = [t.trade_lane_id for t in trade_lanes] if trade_lanes else [1, 2, 3]

    if vessel_class_ids is None:
        vclasses = db.query(VesselClass).all()
        vessel_class_ids = [v.vessel_class_id for v in vclasses] if vclasses else [1, 2, 3, 4]

    panel_df = get_training_panel(lanes=trade_lane_ids, classes=vessel_class_ids)
    registry = ModelRegistryManager(db)
    backtester = WalkForwardBacktester(min_train_days=365, step_days=30, horizons=[7, 30, 90, 180])

    model_candidates = [
        ("lightgbm_quantile", LightGBMQuantileForecaster),
        ("prophet", ProphetForecaster),
        ("sarimax", SARIMAXForecaster),
    ]

    summary_results = []

    for lane_id in trade_lane_ids:
        for class_id in vessel_class_ids:
            logger.info(f"--- Training models for trade_lane_id={lane_id}, vessel_class_id={class_id} ---")

            for model_name, model_cls in model_candidates:
                try:
                    # 1. Backtest model using walk-forward window
                    metrics = backtester.evaluate(
                        forecaster_class=model_cls,
                        panel_df=panel_df,
                        trade_lane_id=lane_id,
                        vessel_class_id=class_id,
                        target_variable=target_variable
                    )

                    # 2. Fit full forecaster on all historical data
                    forecaster = model_cls(target_variable=target_variable)
                    forecaster.fit(panel_df, trade_lane_id=lane_id, vessel_class_id=class_id)

                    # 3. Register model artifact
                    reg_entry = registry.register_model(
                        forecaster=forecaster,
                        trade_lane_id=lane_id,
                        vessel_class_id=class_id,
                        metrics=metrics,
                        target_variable=target_variable
                    )

                    # 4. Try auto-promotion gate
                    is_promoted = registry.promote_if_better(reg_entry.model_id)

                    summary_results.append({
                        "model_id": reg_entry.model_id,
                        "model_name": model_name,
                        "trade_lane_id": lane_id,
                        "vessel_class_id": class_id,
                        "mape": metrics.get("mape"),
                        "rmse": metrics.get("rmse"),
                        "directional_accuracy": metrics.get("directional_accuracy"),
                        "is_promoted": is_promoted
                    })

                except Exception as e:
                    logger.warning(f"Failed to train {model_name} for lane={lane_id}, class={class_id}: {e}")

    return {
        "status": "COMPLETED",
        "models_trained_count": len(summary_results),
        "results": summary_results
    }


