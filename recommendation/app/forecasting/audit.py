from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.db.models import ModelRegistry, TradeLane, VesselClass
from app.features.build_training_panel import get_training_panel


def audit_model_coverage_and_quality(db: Session) -> Dict[str, Any]:
    """
    Produces a complete audit showing:
    - Total training rows & date range
    - Trade lanes, vessel classes, commodities
    - Coverage matrix: which (lane, class) combinations have active champion models vs fallback
    - Model metrics: RMSE, MAPE, Directional Accuracy, Pinball Loss
    """
    panel_df = get_training_panel()
    total_rows = len(panel_df)
    min_date = str(panel_df["date"].min())
    max_date = str(panel_df["date"].max())

    trade_lanes = db.query(TradeLane).all()
    vclasses = db.query(VesselClass).all()

    coverage_matrix = []
    trained_count = 0
    fallback_count = 0

    for lane in trade_lanes:
        for vc in vclasses:
            champ = db.query(ModelRegistry).filter(
                ModelRegistry.target_trade_lane_id == lane.trade_lane_id,
                ModelRegistry.target_vessel_class_id == vc.vessel_class_id,
                ModelRegistry.is_active == True
            ).first()

            row_count = len(panel_df[
                (panel_df["trade_lane_id"] == lane.trade_lane_id) &
                (panel_df["vessel_class_id"] == vc.vessel_class_id)
            ])

            if champ:
                trained_count += 1
                status = "ACTIVE_CHAMPION"
                metrics = champ.metrics_json or {}
                model_name = champ.model_name
                version = champ.version
            else:
                fallback_count += 1
                status = "FALLBACK_NAIVE"
                metrics = {}
                model_name = "naive_fallback"
                version = "0.0.0"

            coverage_matrix.append({
                "trade_lane_id": lane.trade_lane_id,
                "origin_port": lane.origin_port_code,
                "destination_port": lane.destination_port_code,
                "vessel_class_id": vc.vessel_class_id,
                "vessel_class_name": vc.class_name,
                "status": status,
                "model_name": model_name,
                "version": version,
                "training_rows": row_count,
                "mape": metrics.get("mape"),
                "rmse": metrics.get("rmse"),
                "directional_accuracy": metrics.get("directional_accuracy"),
                "pinball_loss": metrics.get("pinball_loss")
            })

    return {
        "dataset_summary": {
            "total_training_rows": total_rows,
            "training_date_start": min_date,
            "training_date_end": max_date,
            "trade_lanes_count": len(trade_lanes),
            "vessel_classes_count": len(vclasses),
            "total_lane_class_combinations": len(coverage_matrix),
            "trained_champions_count": trained_count,
            "fallback_combinations_count": fallback_count
        },
        "coverage_matrix": coverage_matrix
    }
