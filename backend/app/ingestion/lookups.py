"""Shared reference-data lookups for connector normalize() steps.

Connectors receive natural keys from raw sources (port codes, class names,
commodity names) and need the surrogate integer PKs Phase 1's schema uses
as foreign keys. These lookups are built once per connector run and cached
for a short TTL so a Celery Beat cycle doesn't re-query reference tables for
every row, while still picking up reference-data edits within a reasonable
window without a process restart.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Commodity, Port, TradeLane, VesselClass

_TTL_SECONDS = 300  # 5 minutes — reference data changes rarely, this is generous


@dataclass
class _CachedMap:
    loader: Callable[[Session], dict]
    value: dict = field(default_factory=dict)
    loaded_at: float = 0.0

    def get(self, session: Session) -> dict:
        if not self.value or (time.monotonic() - self.loaded_at) > _TTL_SECONDS:
            self.value = self.loader(session)
            self.loaded_at = time.monotonic()
        return self.value


def _load_port_id_by_code(session: Session) -> dict[str, int]:
    rows = session.execute(select(Port.port_code, Port.port_id)).all()
    return {code: port_id for code, port_id in rows}


def _load_vessel_class_id_by_name(session: Session) -> dict[str, int]:
    rows = session.execute(select(VesselClass.class_name, VesselClass.vessel_class_id)).all()
    return {name: class_id for name, class_id in rows}


def _load_commodity_id_by_name(session: Session) -> dict[str, int]:
    rows = session.execute(select(Commodity.commodity_name, Commodity.commodity_id)).all()
    return {name: commodity_id for name, commodity_id in rows}


def _load_trade_lane_id_by_key(session: Session) -> dict[tuple[int, int, str], int]:
    rows = session.execute(
        select(
            TradeLane.origin_port_id,
            TradeLane.destination_port_id,
            TradeLane.commodity,
            TradeLane.trade_lane_id,
        )
    ).all()
    return {(o, d, c): lane_id for o, d, c, lane_id in rows}


_port_id_by_code = _CachedMap(_load_port_id_by_code)
_vessel_class_id_by_name = _CachedMap(_load_vessel_class_id_by_name)
_commodity_id_by_name = _CachedMap(_load_commodity_id_by_name)
_trade_lane_id_by_key = _CachedMap(_load_trade_lane_id_by_key)


class ReferenceDataLookup:
    """Facade a connector holds for the duration of one run()."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def port_id(self, port_code: str) -> int | None:
        return _port_id_by_code.get(self._session).get(port_code)

    def vessel_class_id(self, class_name: str) -> int | None:
        return _vessel_class_id_by_name.get(self._session).get(class_name)

    def commodity_id(self, commodity_name: str) -> int | None:
        return _commodity_id_by_name.get(self._session).get(commodity_name)

    def trade_lane_id(self, origin_port_code: str, destination_port_code: str, commodity: str) -> int | None:
        origin_id = self.port_id(origin_port_code)
        dest_id = self.port_id(destination_port_code)
        if origin_id is None or dest_id is None:
            return None
        return _trade_lane_id_by_key.get(self._session).get((origin_id, dest_id, commodity))

    def all_trade_lanes_for_class_hint(self) -> list[tuple[int, int, str, int]]:
        """Returns (origin_port_id, destination_port_id, commodity, trade_lane_id)
        for every seeded lane — used by connectors (e.g. the BDI proxy) whose
        source series is not itself lane-specific and must be broadcast."""
        table = _trade_lane_id_by_key.get(self._session)
        return [(o, d, c, lane_id) for (o, d, c), lane_id in table.items()]
