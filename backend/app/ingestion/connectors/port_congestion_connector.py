"""Indian Ports Association (IPA) congestion connector.

IPA port-wise traffic statistics are public but published as PDF/tabular
reports needing scraping/digitization (Section 2.1.B) — stubbed with a
synthetic fallback per the agent instruction in Section 2.1.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.db.models import PortCongestion
from app.ingestion.base_connector import BaseSourceConnector
from app.ingestion.exceptions import SourceUnavailableError
from app.ingestion.lookups import ReferenceDataLookup
from app.ingestion.synthetic import SyntheticDataGenerator
from app.ingestion.validation.expectations import PortCongestionSchema

# ECI ports we track congestion for.
TRACKED_PORT_CODES = ["INPRT", "INVTZ"]


class PortCongestionConnector(BaseSourceConnector):
    name = "port_congestion_connector"
    default_provenance = "proxy"

    def fetch(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        try:
            raw = self._parse_ipa_reports(start, as_of)
        except Exception as exc:
            raise SourceUnavailableError(self.name, str(exc), series="port_congestion") from exc
        return raw

    def _parse_ipa_reports(self, start: date, end: date) -> pd.DataFrame:
        """TODO: fetch and parse IPA's published traffic-statistics
        PDF/tabular reports (ipa.nic.in) into vessels_waiting /
        avg_waiting_days per port per day."""
        raise NotImplementedError("IPA report parser not yet implemented")

    def fallback(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        gen = SyntheticDataGenerator()

        session = self._session_factory()
        try:
            lookup = ReferenceDataLookup(session)
            port_ids = [pid for code in TRACKED_PORT_CODES if (pid := lookup.port_id(code)) is not None]
        finally:
            session.close()

        if not port_ids:
            return pd.DataFrame()
        return gen.port_congestion(port_ids=port_ids, start=start, end=as_of)

    def validate(self, raw: pd.DataFrame) -> pd.DataFrame:
        if raw.empty:
            return raw
        return PortCongestionSchema.validate(raw)

    def normalize(self, validated: pd.DataFrame) -> list[PortCongestion]:
        return [
            PortCongestion(
                time=row.time,
                port_id=int(row.port_id),
                vessels_waiting=None if pd.isna(row.vessels_waiting) else int(row.vessels_waiting),
                avg_waiting_days=row.avg_waiting_days,
                data_provenance=row.data_provenance,
            )
            for row in validated.itertuples(index=False)
        ]
