import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ModelRegistry
from app.forecasting.base_forecaster import BaseForecaster
from app.forecasting.models.lightgbm_quantile import LightGBMQuantileForecaster
from app.forecasting.models.prophet_model import ProphetForecaster
from app.forecasting.models.sarimax_model import SARIMAXForecaster

logger = logging.getLogger(__name__)


MODEL_CLASS_MAP = {
    "lightgbm_quantile": LightGBMQuantileForecaster,
    "prophet": ProphetForecaster,
    "sarimax": SARIMAXForecaster,
}


class ModelRegistryManager:
    """
    Model Registry Manager for FreightIQ.
    Handles registering trained model artifacts, metrics, and managing promotion logic (>2% MAPE gate).
    """

    def __init__(self, db: Session):
        self.db = db
        self.artifacts_dir = settings.ARTIFACTS_DIR
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def register_model(
        self,
        forecaster: BaseForecaster,
        trade_lane_id: int,
        vessel_class_id: int,
        metrics: Dict[str, Any],
        target_variable: str = "TCE_rate",
        target_horizon_days: Optional[int] = None,
    ) -> ModelRegistry:
        """
        Saves forecaster artifact to disk and registers row in model_registry DB table.
        """
        import uuid
        model_id = str(uuid.uuid4())
        artifact_name = f"{forecaster.model_name}_lane{trade_lane_id}_class{vessel_class_id}_{model_id[:8]}.joblib"
        artifact_path = str(self.artifacts_dir / artifact_name)

        forecaster.save(artifact_path)

        reg_entry = ModelRegistry(
            model_id=model_id,
            model_name=forecaster.model_name,
            model_type=forecaster.model_name,
            target_trade_lane_id=trade_lane_id,
            target_vessel_class_id=vessel_class_id,
            target_horizon_days=target_horizon_days,
            target_variable=target_variable,
            version=forecaster.version,
            artifact_path=artifact_path,
            metrics_json=metrics,
            is_active=False,  # Unactive by default until promotion gate check
        )

        self.db.add(reg_entry)
        self.db.commit()
        self.db.refresh(reg_entry)
        logger.info(f"Registered model {reg_entry.model_id} ({forecaster.model_name}) with MAPE={metrics.get('mape')}%")
        return reg_entry

    def promote_if_better(
        self,
        challenger_id: str,
        min_improvement_pct: float = settings.DEFAULT_RETRAIN_MARGIN_PCT
    ) -> bool:
        """
        Promotion Gate: Promotes challenger to active if its held-out MAPE strictly improves
        over the current champion by at least `min_improvement_pct` (e.g. 2%).
        """
        challenger = self.db.query(ModelRegistry).filter(ModelRegistry.model_id == challenger_id).first()
        if not challenger:
            raise ValueError(f"Challenger model_id={challenger_id} not found.")

        # Find current active champion for this (lane, class)
        champion = self.db.query(ModelRegistry).filter(
            ModelRegistry.target_trade_lane_id == challenger.target_trade_lane_id,
            ModelRegistry.target_vessel_class_id == challenger.target_vessel_class_id,
            ModelRegistry.target_variable == challenger.target_variable,
            ModelRegistry.is_active == True
        ).first()

        challenger_mape = (challenger.metrics_json or {}).get("mape", 999.0)

        if champion is None:
            # No champion exists — auto-promote challenger
            challenger.is_active = True
            self.db.commit()
            logger.info(f"Promoted challenger {challenger_id} to ACTIVE (first champion for lane={challenger.target_trade_lane_id})")
            return True

        champion_mape = (champion.metrics_json or {}).get("mape", 999.0)
        mape_delta_pct = champion_mape - challenger_mape

        if mape_delta_pct >= min_improvement_pct:
            champion.is_active = False
            challenger.is_active = True
            self.db.commit()
            logger.info(f"PROMOTED challenger {challenger_id} (MAPE={challenger_mape:.2f}%) over champion {champion.model_id} (MAPE={champion_mape:.2f}%), delta={mape_delta_pct:.2f}% >= {min_improvement_pct}%")
            return True
        else:
            logger.info(f"REJECTED challenger {challenger_id} (MAPE={challenger_mape:.2f}%). Champion {champion.model_id} remains active (MAPE={champion_mape:.2f}%), delta={mape_delta_pct:.2f}% < {min_improvement_pct}%")
            return False

    def get_active_model(self, trade_lane_id: int, vessel_class_id: int, target_variable: str = "TCE_rate") -> Tuple[Optional[BaseForecaster], Optional[ModelRegistry], str]:
        """
        Loads the active champion forecaster instance and DB metadata row.
        Performs hierarchical lookup:
        1. Exact match (lane_id, class_id)
        2. Class champion (class_id)
        3. Lane champion (lane_id)
        4. Global champion
        Returns (forecaster, active_entry, lookup_reason).
        """
        # 1. Exact match
        active_entry = self.db.query(ModelRegistry).filter(
            ModelRegistry.target_trade_lane_id == trade_lane_id,
            ModelRegistry.target_vessel_class_id == vessel_class_id,
            ModelRegistry.target_variable == target_variable,
            ModelRegistry.is_active == True
        ).first()

        lookup_reason = f"Exact match active champion for trade_lane_id={trade_lane_id}, vessel_class_id={vessel_class_id}"

        # 2. Class match fallback
        if not active_entry:
            active_entry = self.db.query(ModelRegistry).filter(
                ModelRegistry.target_vessel_class_id == vessel_class_id,
                ModelRegistry.target_variable == target_variable,
                ModelRegistry.is_active == True
            ).first()
            if active_entry:
                lookup_reason = f"Class champion match for vessel_class_id={vessel_class_id} (lane {trade_lane_id} not explicitly trained)"

        # 3. Lane match fallback
        if not active_entry:
            active_entry = self.db.query(ModelRegistry).filter(
                ModelRegistry.target_trade_lane_id == trade_lane_id,
                ModelRegistry.target_variable == target_variable,
                ModelRegistry.is_active == True
            ).first()
            if active_entry:
                lookup_reason = f"Lane champion match for trade_lane_id={trade_lane_id} (class {vessel_class_id} not explicitly trained)"

        # 4. Global match fallback
        if not active_entry:
            active_entry = self.db.query(ModelRegistry).filter(
                ModelRegistry.target_variable == target_variable,
                ModelRegistry.is_active == True
            ).first()
            if active_entry:
                lookup_reason = f"Global active champion fallback model"

        if not active_entry:
            return None, None, f"No active champion model found in model_registry for trade_lane_id={trade_lane_id}, vessel_class_id={vessel_class_id}"

        try:
            model_cls = MODEL_CLASS_MAP.get(active_entry.model_type, LightGBMQuantileForecaster)
            forecaster = model_cls.load(active_entry.artifact_path)
            return forecaster, active_entry, f"None: {lookup_reason} ('{active_entry.model_name}' v{active_entry.version})"
        except Exception as e:
            logger.error(f"Failed to load artifact at {active_entry.artifact_path}: {e}")
            return None, None, f"Failed to load model artifact ({e})"


