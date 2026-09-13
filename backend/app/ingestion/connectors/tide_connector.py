"""INCOIS / NOAA tide connector.

Feeds the tide-adjusted draft feasibility logic (Section 5.1):
    effective_draft(port, t) = charted_draft + tide_height_m(port, t) - safety_margin

INCOIS (Indian ocean-specific) and NOAA (global reference / Open-Meteo
fallback) are both free (Section 2.1.D) but not yet wired up here — stubbed
with a synthetic fallback so the draft-feasibility pipeline has *something*
to compute against from Phase 2 onward, per Section 6's directive that
tide-adjusted draft feasibility must be in place from Phase 1/2, not bolted
on later.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.db.models import Port, TideLevel
from app.ingestion.base_connector import BaseSourceConnector
from app.ingestion.exceptions import SourceUnavailableError
from app.ingestion.lookups import ReferenceDataLookup
from app.ingestion.synthetic import SyntheticDataGenerator
from app.ingestion.validation.expectations import TideLevelSchema

TRACKED_PORT_CODES = ["INPRT", "INVTZ"]


class TideConnector(BaseSourceConnector):
    name = "tide_connector"
    default_provenance = "proxy"

    def fetch(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        if not settings.incois_api_key:
            raise SourceUnavailableError(self.name, "INCOIS_API_KEY not configured", series="tide_levels")
        try:
            raw = self._fetch_incois(start, as_of)
        except Exception as exc:
            raise SourceUnavailableError(self.name, str(exc), series="tide_levels") from exc
        return raw

    def _fetch_incois(self, start: date, end: date) -> pd.DataFrame:
        """TODO: call INCOIS's tide-prediction service for each tracked port."""
        raise NotImplementedError("INCOIS tide fetch not yet implemented")

    def fallback(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        gen = SyntheticDataGenerator()

        session = self._session_factory()
        try:
            lookup = ReferenceDataLookup(session)
            rows = []
            for code in TRACKED_PORT_CODES:
                pid = lookup.port_id(code)
                if pid is None:
                    continue
                port = session.get(Port, pid)
                tidal_range = float(port.tidal_range_m) if port and port.tidal_range_m else 3.0
                rows.append((pid, tidal_range))
        finally:
            session.close()

        frames = [
            gen.tide_levels(port_ids=[pid], start=start, end=as_of, tidal_range_m=tidal_range)
            for pid, tidal_range in rows
        ]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def validate(self, raw: pd.DataFrame) -> pd.DataFrame:
        if raw.empty:
            return raw
        return TideLevelSchema.validate(raw)

    def normalize(self, validated: pd.DataFrame) -> list[TideLevel]:
        return [
            TideLevel(
                time=row.time,
                port_id=int(row.port_id),
                tide_height_m=row.tide_height_m,
                data_provenance=row.data_provenance,
            )
            for row in validated.itertuples(index=False)
        ]
