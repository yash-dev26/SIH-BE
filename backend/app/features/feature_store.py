"""BaseFeatureStore interface (Phase 2 file deliverable).

MVP implementation reads/writes the `feature_snapshots` Postgres table.
Swapping in real Feast later is meant to be a config change: any future
`FeastFeatureStore(BaseFeatureStore)` just needs to implement the same two
methods against a Feast online/offline store instead of Postgres.
"""

from __future__ import annotations

import abc
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.features.models import FeatureSnapshot


class FeatureEntity(NamedTuple):
    trade_lane_id: int
    vessel_class_id: int


class BaseFeatureStore(abc.ABC):
    @abc.abstractmethod
    def get_features(self, entity: FeatureEntity, as_of: datetime, feature_group: str) -> dict | None:
        """Return the stored feature dict for this entity/as_of/group, or
        None if no snapshot exists yet."""

    @abc.abstractmethod
    def write_features(
        self, entity: FeatureEntity, as_of: datetime, feature_group: str, features: dict
    ) -> None:
        """Upsert a feature snapshot. Writing the same (entity, as_of, group)
        twice overwrites — snapshots are keyed by content, not append-only,
        since re-running a pipeline for the same as_of date should produce
        the same features (idempotent), not a growing history of drafts."""


class PostgresFeatureStore(BaseFeatureStore):
    def __init__(self, session_factory=None) -> None:
        if session_factory is None:
            from app.db.session import SessionLocal

            session_factory = SessionLocal
        self._session_factory = session_factory

    def get_features(self, entity: FeatureEntity, as_of: datetime, feature_group: str) -> dict | None:
        session: Session = self._session_factory()
        try:
            row = session.execute(
                select(FeatureSnapshot).where(
                    FeatureSnapshot.trade_lane_id == entity.trade_lane_id,
                    FeatureSnapshot.vessel_class_id == entity.vessel_class_id,
                    FeatureSnapshot.as_of == as_of,
                    FeatureSnapshot.feature_group == feature_group,
                )
            ).scalar_one_or_none()
            return row.features if row is not None else None
        finally:
            session.close()

    def write_features(
        self, entity: FeatureEntity, as_of: datetime, feature_group: str, features: dict
    ) -> None:
        session: Session = self._session_factory()
        try:
            stmt = pg_insert(FeatureSnapshot).values(
                trade_lane_id=entity.trade_lane_id,
                vessel_class_id=entity.vessel_class_id,
                as_of=as_of,
                feature_group=feature_group,
                features=features,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_feature_snapshot_entity_asof_group",
                set_={"features": stmt.excluded.features},
            )
            session.execute(stmt)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
