"""Celery application instance.

Phase 1 scope: just the app object so `docker compose up` brings up a worker
that can be inspected/health-checked. Task modules (ingestion connectors in
Phase 2, model training in Phase 3, MILP solves in Phase 4, drift monitoring
in Section 5.4) are registered via `include=[...]` as each phase lands —
kept as an empty list here rather than pre-importing modules that don't exist yet.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "freightiq",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
