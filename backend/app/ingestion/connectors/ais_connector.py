"""AISHub / MarineTraffic AIS position connector.

AISHub requires reciprocal data-sharing/sponsorship, MarineTraffic is
freemium/paid (Section 2.1.C) — stubbed with a synthetic fallback. This
feeds the fleet-supply-proxy feature group (Section 3.1) once real vessel
tracking is wired up.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from geoalchemy2.elements import WKTElement

from app.config import settings
from app.db.models import AisPosition
from app.ingestion.base_connector import BaseSourceConnector
from app.ingestion.exceptions import SourceUnavailableError
from app.ingestion.synthetic import SyntheticDataGenerator
from app.ingestion.validation.expectations import AisPositionSchema

# Placeholder fleet used until real vessels are seeded/tracked; swap for a
# query against `vessels` once Phase 1's vessel roster is populated.
PLACEHOLDER_IMO_NUMBERS = ["9123456", "9234567", "9345678"]


class AisConnector(BaseSourceConnector):
    name = "ais_connector"
    default_provenance = "proxy"

    def fetch(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        if not (settings.aishub_api_key or settings.marinetraffic_api_key):
            raise SourceUnavailableError(self.name, "no AIS provider API key configured", series="ais_positions")
        try:
            raw = self._fetch_aishub_or_marinetraffic(start, as_of)
        except Exception as exc:
            raise SourceUnavailableError(self.name, str(exc), series="ais_positions") from exc
        return raw

    def _fetch_aishub_or_marinetraffic(self, start: date, end: date) -> pd.DataFrame:
        """TODO: call AISHub first (free, reciprocal), fall back to
        MarineTraffic if a paid key is configured and AISHub is unavailable."""
        raise NotImplementedError("AIS provider fetch not yet implemented")

    def fallback(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        gen = SyntheticDataGenerator()
        return gen.ais_positions(imo_numbers=PLACEHOLDER_IMO_NUMBERS, start=start, end=as_of)

    def validate(self, raw: pd.DataFrame) -> pd.DataFrame:
        if raw.empty:
            return raw
        return AisPositionSchema.validate(raw)

    def normalize(self, validated: pd.DataFrame) -> list[AisPosition]:
        rows = []
        for row in validated.itertuples(index=False):
            point = WKTElement(f"POINT({row.longitude} {row.latitude})", srid=4326)
            rows.append(
                AisPosition(
                    time=row.time,
                    imo_number=row.imo_number,
                    location=point,
                    speed_knots=row.speed_knots,
                    heading=row.heading,
                    nav_status=row.nav_status,
                    data_provenance=row.data_provenance,
                )
            )
        return rows
