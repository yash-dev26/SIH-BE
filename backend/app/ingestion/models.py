"""New persistence introduced by Phase 2: the data_quality_log table.

Phase 1's models.py did not include this table, so it's added here rather
than editing the Phase 1 file. Wire it into Alembic via
alembic/versions/0002_phase2_ingestion_and_features.py.

NOTE ON THE `Base` IMPORT: Phase 1 didn't confirm where `Base` (the
declarative base all ORM models inherit from) is defined. This assumes the
common layout `app/db/base.py`, falling back to `app/db/models.py` if that
module doesn't exist. Adjust the import below if your project defines it
elsewhere (e.g. `app/db/__init__.py`).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

try:
    from app.db.base import Base
except ImportError:  # pragma: no cover
    from app.db.models import Base  # type: ignore[no-redef]


class DataQualityLog(Base):
    """Audit trail of every ingestion event where a connector degraded to a
    fallback tier, failed outright, or otherwise deserves a flag.

    One row per connector.run() outcome that isn't a clean "live data,
    wrote N rows" success — keeps the happy path quiet and the exceptions
    visible, per Section 5.3's layered fallback chain.
    """

    __tablename__ = "data_quality_log"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    connector_name: Mapped[str] = mapped_column(String(80), nullable=False)
    # 'fallback_used' | 'failed' | 'validation_error' | 'partial_success'
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    # Provenance tier the data actually ended up at after fallback resolution.
    resolved_provenance: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(500))
    rows_written: Mapped[int | None] = mapped_column(Integer)
    # Arbitrary run kwargs / series identifiers for later analysis.
    context: Mapped[dict | None] = mapped_column(JSONB)
