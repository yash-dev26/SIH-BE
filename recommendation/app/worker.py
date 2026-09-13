import logging
from celery import Celery

from app.config import settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

celery_app = Celery(
    "freightiq_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_routes={
        "app.worker.train_models_task": {"queue": "training"},
        "app.worker.run_batch_optimization_task": {"queue": "optimization"},
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)


@celery_app.task(name="app.worker.train_models_task", bind=True)
def train_models_task(self, trade_lane_ids=None, vessel_class_ids=None, target_variable="TCE_rate"):
    """
    Celery background task for training forecasters.
    """
    from app.forecasting.training_job import run_model_training_pipeline
    db = SessionLocal()
    try:
        res = run_model_training_pipeline(
            db=db,
            trade_lane_ids=trade_lane_ids,
            vessel_class_ids=vessel_class_ids,
            target_variable=target_variable
        )
        return res
    finally:
        db.close()


@celery_app.task(name="app.worker.run_batch_optimization_task", bind=True)
def run_batch_optimization_task(self, parcels, spot_cap_ratio=0.4):
    """
    Celery background task for the Phase 4 "full solver" - the CP-SAT multi-parcel
    MILP (app.optimization.milp_solver) - so it never blocks the API request thread.
    `parcels` must be JSON-serializable dicts (dates as ISO strings), since the task
    is submitted through Celery's json serializer.
    """
    from app.optimization.recommendation_service import RecommendationService
    db = SessionLocal()
    try:
        svc = RecommendationService(db)
        return svc.generate_multi_parcel_recommendation(parcels=parcels, spot_cap_ratio=spot_cap_ratio)
    finally:
        db.close()



