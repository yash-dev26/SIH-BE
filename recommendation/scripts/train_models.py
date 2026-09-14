import sys
import os
import logging

# Ensure parent directory (recommendation root) is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging to print live progress to terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("TrainML")

def main():
    logger.info("=========================================================")
    logger.info("  FreightIQ / Recommendation ML Model Training Pipeline  ")
    logger.info("=========================================================")
    
    from app.db.session import SessionLocal, init_db
    from app.forecasting.training_job import run_model_training_pipeline
    
    db = SessionLocal()
    init_db(db)
    
    logger.info("Starting ML Training Pipeline using real dataset in dataset/ folder...")
    
    # Run full training pipeline for all trade lanes and vessel classes
    res = run_model_training_pipeline(db=db)
    
    logger.info("=========================================================")
    logger.info(f" Training Completed with Status: {res.get('status')}")
    logger.info(f" Total Models Processed: {res.get('models_trained_count')}")
    logger.info(" Summary of Results:")
    for item in res.get("results", []):
        lane = item.get("trade_lane_id")
        vclass = item.get("vessel_class_id")
        model_name = item.get("model_name")
        mape = item.get("mape")
        promoted = "YES (CHAMPION)" if item.get("is_promoted") else "No"
        logger.info(f"   Lane {lane} | Vessel Class {vclass} | {model_name:<18} | MAPE: {mape:6.2f}% | Promoted: {promoted}")
    logger.info("=========================================================")

if __name__ == "__main__":
    main()
