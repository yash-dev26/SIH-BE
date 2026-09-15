"""
FreightIQ — Phase 3 (Model Training & Inference Engine) End-to-End Walkthrough Script
"""
from datetime import date
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.forecasting.inference_service import ForecastingService
from app.forecasting.training_job import run_model_training_pipeline
from app.forecasting.registry import ModelRegistryManager


def main():
    print("===========================================================")
    print(" FreightIQ — Phase 3 Model Training & Inference Engine Demo")
    print("===========================================================\n")

    db: Session = SessionLocal()
    init_db(db)

    # 1. Check inference BEFORE model training (Graceful Degradation / Naive Fallback)
    print("1. Querying forecast BEFORE model training (Naive Fallback test)...")
    service = ForecastingService(db)
    fallback_forecasts = service.get_forecast(trade_lane_id=1, vessel_class_id=3, horizons=[7, 30, 90, 180])

    print("   [+] Received Naive Fallback Forecasts:")
    for f in fallback_forecasts:
        print(f"       -> Horizon {f.horizon_days}d ({f.target_date}): Point=${f.point_forecast:.2f}/day | p10=${f.p10:.2f} | p90=${f.p90:.2f} | Model={f.model_version}")

    # 2. Run Model Training Pipeline
    print("\n2. Executing Model Training Pipeline (LightGBM Quantile + Prophet + SARIMAX + Backtesting)...")
    training_summary = run_model_training_pipeline(
        db=db,
        trade_lane_ids=[1, 2],
        vessel_class_ids=[2, 3],
        target_variable="TCE_rate"
    )

    print(f"   [+] Training Complete! Total models trained: {training_summary['models_trained_count']}")
    for res in training_summary["results"]:
        status = "PROMOTED CHAMPION" if res["is_promoted"] else "Candidate (Not Promoted)"
        print(f"       -> Model: {res['model_name']:<18} | Lane: {res['trade_lane_id']} Class: {res['vessel_class_id']} | MAPE: {res['mape']:.2f}% | Status: {status}")

    # 3. Check active model champion in registry
    print("\n3. Inspecting Model Registry Champion...")
    registry = ModelRegistryManager(db)
    active_forecaster, active_meta = registry.get_active_model(trade_lane_id=1, vessel_class_id=3)
    if active_meta:
        print(f"   [+] Active Champion: {active_meta.model_name} (Version: {active_meta.version}, ID: {active_meta.model_id})")
        print(f"       Metrics JSON: {active_meta.metrics_json}")

    # 4. Query forecast AFTER model training (Active Champion Inference)
    print("\n4. Querying forecast AFTER model training (Champion Model Inference)...")
    champion_forecasts = service.get_forecast(trade_lane_id=1, vessel_class_id=3, horizons=[7, 30, 90, 180])

    print("   [+] Received Champion Model Forecasts:")
    for f in champion_forecasts:
        print(f"       -> Horizon {f.horizon_days}d ({f.target_date}): Point=${f.point_forecast:.2f}/day | p10=${f.p10:.2f} | p90=${f.p90:.2f} | Model ID={f.model_id[:8]}")
        print(f"          Feature Audit Snapshot Keys: {list(f.feature_snapshot.keys())[:5]}...")

    print("\n===========================================================")
    print(" Phase 3 Walkthrough Demo Complete Successfully!")
    print("===========================================================")


if __name__ == "__main__":
    main()


