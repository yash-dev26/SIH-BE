"""New persistence introduced by Phase 2: the feature_snapshots table.

Phase 1's schema stores a per-forecast feature snapshot inline
(`Forecast.feature_snapshot` JSONB) for auditability of *what a specific
forecast saw*. This table is different: it's the Feast-compatible MVP
feature store itself — versioned feature vectors per (trade_lane, vessel
class, as_of date), independent of any one forecast run, so the training
pipeline (Phase 3) can pull a reproducible panel without recomputing
everything from raw tables each time.

NOTE ON THE `Base` IMPORT: same caveat as app/ingestion/models.py — adjust
if your project defines `Base` somewhere other than app/db/base.py.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

try:
    from app.db.base import Base
except ImportError:  # pragma: no cover
    from app.db.models import Base  # type: ignore[no-redef]


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "trade_lane_id", "vessel_class_id", "as_of", "feature_group",
            name="uq_feature_snapshot_entity_asof_group",
        ),
    )

    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_lane_id: Mapped[int] = mapped_column(ForeignKey("trade_lanes.trade_lane_id"), nullable=False)
    vessel_class_id: Mapped[int] = mapped_column(ForeignKey("vessel_classes.vessel_class_id"), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # 'lag' | 'seasonality' | 'macro' | 'full_panel' — lets the feature store
    # cache intermediate groups as well as the final joined panel row.
    feature_group: Mapped[str] = mapped_column(String(30), nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
