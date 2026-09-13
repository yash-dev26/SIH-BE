"""Ship & Bunker price connector.

Ship&Bunker publishes VLSFO/IFO380/MGO prices freely but with no formal API
(Section 2.1.D) — this is a scrape-shaped connector, stubbed with a clear
TODO and a synthetic fallback, per the agent instruction in Section 2.1.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.db.models import BunkerPrice
from app.ingestion.base_connector import BaseSourceConnector
from app.ingestion.exceptions import SourceUnavailableError
from app.ingestion.lookups import ReferenceDataLookup
from app.ingestion.synthetic import SyntheticDataGenerator
from app.ingestion.validation.expectations import BunkerPriceSchema

# ECI bunkering hubs we care about; None = global reference price row.
TRACKED_PORT_CODES: list[str | None] = [None, "INVTZ", "INPRT"]


class BunkerPriceConnector(BaseSourceConnector):
    name = "bunker_price_connector"
    default_provenance = "proxy"

    def fetch(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        try:
            raw = self._scrape_ship_and_bunker(start, as_of)
        except Exception as exc:
            raise SourceUnavailableError(self.name, str(exc), series="bunker_prices") from exc
        return raw

    def _scrape_ship_and_bunker(self, start: date, end: date) -> pd.DataFrame:
        """TODO: implement the shipandbunker.com scrape.

        Left unimplemented (raises) so the orchestrator's fallback path is
        exercised deterministically until a scraper is wired up; ship&bunker
        has no formal API so this will need an HTML parser (e.g. selectolax
        or BeautifulSoup) against their published price tables.
        """
        raise NotImplementedError("Ship&Bunker scraper not yet implemented")

    def fallback(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        gen = SyntheticDataGenerator()

        session = self._session_factory()
        try:
            lookup = ReferenceDataLookup(session)
            port_ids: list[int | None] = []
            for code in TRACKED_PORT_CODES:
                if code is None:
                    port_ids.append(None)
                else:
                    pid = lookup.port_id(code)
                    if pid is not None:
                        port_ids.append(pid)
        finally:
            session.close()

        return gen.bunker_prices(port_ids=port_ids, start=start, end=as_of)

    def validate(self, raw: pd.DataFrame) -> pd.DataFrame:
        if raw.empty:
            return raw
        return BunkerPriceSchema.validate(raw)

    def normalize(self, validated: pd.DataFrame) -> list[BunkerPrice]:
        return [
            BunkerPrice(
                time=row.time,
                port_id=None if pd.isna(row.port_id) else int(row.port_id),
                fuel_grade=row.fuel_grade,
                price_usd_per_mt=row.price_usd_per_mt,
                data_provenance=row.data_provenance,
            )
            for row in validated.itertuples(index=False)
        ]
