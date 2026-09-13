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
