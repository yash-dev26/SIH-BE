"""FastAPI app instantiation. Phase 1 scope: app skeleton + health checks only.
The `/forecast /recommend /risk /ports /vessels` REST surface (Section 1.2)
is built out in Phase 5 once the Forecasting and Optimization engines exist."""

import structlog
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db

settings = get_settings()
logger = structlog.get_logger()

app = FastAPI(
    title="FreightIQ",
    description="Intelligent Freight Forecasting & Vessel Chartering Optimization Platform",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
def health() -> dict:
    """Liveness check — no external dependencies. Should always return 200 if the process is up."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)) -> dict:
    """Readiness check — confirms the DB is reachable and reports row counts per
    core table, per the Phase 1 acceptance check:
    `curl localhost:8000/health/db` returns row counts per table > 0 after seeding."""
    tables = [
        "vessel_classes",
        "ports",
        "trade_lanes",
        "commodities",
        "freight_rates",
        "bunker_prices",
        "commodity_prices",
        "port_congestion",
        "tide_levels",
        "ais_positions",
        "vessels",
        "charter_contracts",
        "voyage_simulations",
        "model_registry",
        "forecasts",
        "recommendations",
    ]

    row_counts: dict[str, int] = {}
    try:
        for table_name in tables:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))  # noqa: S608
            row_counts[table_name] = result.scalar_one()
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any DB failure means "not ready"
        logger.error("health_db_check_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="Database not reachable or not migrated") from exc

    return {"status": "ok", "row_counts": row_counts}
