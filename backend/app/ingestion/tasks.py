"""Celery Beat scheduled tasks: one daily ingestion task per connector
(Phase 2 file deliverable).

IMPORTANT — wiring required in Phase 1's app/celery_app.py:
    Phase 1 currently instantiates `celery_app` with `include=[]`. Add this
    module so the worker process discovers these tasks:

        celery_app = Celery(
            "freightiq",
            broker=settings.celery_broker_url,
            backend=settings.celery_result_backend,
            include=["app.ingestion.tasks"],
        )

    And register the beat schedule (either in celery_app.py's `conf.beat_schedule`
    or here via `celery_app.conf.beat_schedule.update(...)`— done below so
    Phase 1's file doesn't need further edits beyond the `include` line):

        celery -A app.celery_app worker --loglevel=info
        celery -A app.celery_app beat --loglevel=info
"""

from __future__ import annotations

import logging
from datetime import date

from celery.schedules import crontab

from app.celery_app import celery_app
from app.ingestion.connectors.ais_connector import AisConnector
from app.ingestion.connectors.bdi_proxy_connector import BdiProxyConnector
from app.ingestion.connectors.bunker_price_connector import BunkerPriceConnector
from app.ingestion.connectors.commodity_price_connector import CommodityPriceConnector
from app.ingestion.connectors.port_congestion_connector import PortCongestionConnector
from app.ingestion.connectors.tide_connector import TideConnector

logger = logging.getLogger(__name__)

_CONNECTORS = {
    "bdi_proxy": BdiProxyConnector,
    "bunker_price": BunkerPriceConnector,
    "commodity_price": CommodityPriceConnector,
    "ais": AisConnector,
    "port_congestion": PortCongestionConnector,
    "tide": TideConnector,
}


def _run_connector(key: str) -> dict:
    connector_cls = _CONNECTORS[key]
    connector = connector_cls()
    result = connector.run(as_of=date.today(), lookback_days=1)
    logger.info(
        "ingestion_task_complete connector=%s provenance=%s rows=%d fallback_used=%s error=%s",
        result.connector_name,
        result.provenance,
        result.rows_written,
        result.fallback_used,
        result.error,
    )
    return {
        "connector": result.connector_name,
        "provenance": result.provenance,
        "rows_written": result.rows_written,
        "fallback_used": result.fallback_used,
        "error": result.error,
    }


@celery_app.task(name="ingestion.run_bdi_proxy")
def run_bdi_proxy() -> dict:
    return _run_connector("bdi_proxy")


@celery_app.task(name="ingestion.run_bunker_price")
def run_bunker_price() -> dict:
    return _run_connector("bunker_price")


@celery_app.task(name="ingestion.run_commodity_price")
def run_commodity_price() -> dict:
    return _run_connector("commodity_price")


@celery_app.task(name="ingestion.run_ais")
def run_ais() -> dict:
    return _run_connector("ais")


@celery_app.task(name="ingestion.run_port_congestion")
def run_port_congestion() -> dict:
    return _run_connector("port_congestion")


@celery_app.task(name="ingestion.run_tide")
def run_tide() -> dict:
    return _run_connector("tide")


@celery_app.task(name="ingestion.run_all")
def run_all() -> list[dict]:
    """Convenience task: runs every connector once, in sequence. Used by the
    Phase 2 acceptance check (`celery -A app.worker beat` + `worker` for one
    cycle) and by manual/local smoke testing."""
    return [_run_connector(key) for key in _CONNECTORS]


# Daily ingestion schedule — AIS is the exception at a tighter interval
# since vessel positions are far more time-sensitive than daily rate/price
# series. Registered here (rather than requiring edits to Phase 1's
# celery_app.py) via `conf.beat_schedule.update`.
celery_app.conf.beat_schedule = {
    **(getattr(celery_app.conf, "beat_schedule", {}) or {}),
    "ingest-bdi-proxy-daily": {"task": "ingestion.run_bdi_proxy", "schedule": crontab(hour=1, minute=0)},
    "ingest-bunker-price-daily": {"task": "ingestion.run_bunker_price", "schedule": crontab(hour=1, minute=15)},
    "ingest-commodity-price-daily": {"task": "ingestion.run_commodity_price", "schedule": crontab(hour=1, minute=30)},
    "ingest-port-congestion-daily": {"task": "ingestion.run_port_congestion", "schedule": crontab(hour=1, minute=45)},
    "ingest-tide-daily": {"task": "ingestion.run_tide", "schedule": crontab(hour=2, minute=0)},
    "ingest-ais-hourly": {"task": "ingestion.run_ais", "schedule": crontab(minute=0)},
}
