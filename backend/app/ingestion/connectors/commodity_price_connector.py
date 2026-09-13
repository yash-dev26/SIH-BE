"""World Bank Pink Sheet / EIA commodity price connector.

Covers thermal coal, coking coal, and iron ore reference prices
(Section 2.1.D). World Bank Pink Sheet is free monthly CSV; EIA is a free
API for energy-adjacent series — both are treated as the MVP substitute for
paid IHS/Argus/Platts coal indices.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.db.models import CommodityPrice
from app.ingestion.base_connector import BaseSourceConnector
from app.ingestion.exceptions import SourceUnavailableError
from app.ingestion.lookups import ReferenceDataLookup
from app.ingestion.synthetic import SyntheticDataGenerator
from app.ingestion.validation.expectations import CommodityPriceSchema

TRACKED_COMMODITIES = ["thermal_coal", "coking_coal", "iron_ore"]


class CommodityPriceConnector(BaseSourceConnector):
    name = "commodity_price_connector"
    default_provenance = "proxy"

    def fetch(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        try:
            world_bank = self._fetch_world_bank_pink_sheet(start, as_of)
            eia = self._fetch_eia(start, as_of)
        except Exception as exc:
            raise SourceUnavailableError(self.name, str(exc), series="commodity_prices") from exc
        return pd.concat([world_bank, eia], ignore_index=True) if (world_bank is not None or eia is not None) else pd.DataFrame()

    def _fetch_world_bank_pink_sheet(self, start: date, end: date):
        """TODO: download & parse the World Bank Pink Sheet monthly CSV."""
        raise NotImplementedError("World Bank Pink Sheet fetch not yet implemented")

    def _fetch_eia(self, start: date, end: date):
        """TODO: call the free EIA API (requires settings.eia_api_key)."""
        if not settings.eia_api_key:
            raise SourceUnavailableError(self.name, "EIA_API_KEY not configured", series="eia_energy_prices")
        raise NotImplementedError("EIA API fetch not yet implemented")

    def fallback(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        gen = SyntheticDataGenerator()

        session = self._session_factory()
        try:
            lookup = ReferenceDataLookup(session)
            base_prices = {"thermal_coal": 105.0, "coking_coal": 220.0, "iron_ore": 110.0}
            commodity_ids, bases = [], []
            for name, base in base_prices.items():
                cid = lookup.commodity_id(name)
                if cid is not None:
                    commodity_ids.append(cid)
                    bases.append(base)
        finally:
            session.close()

        if not commodity_ids:
            return pd.DataFrame()

        # Generate per-commodity so each keeps its own realistic base level.
        frames = [
            gen.commodity_prices(commodity_ids=[cid], start=start, end=as_of, base_price=base)
            for cid, base in zip(commodity_ids, bases)
        ]
        return pd.concat(frames, ignore_index=True)

    def validate(self, raw: pd.DataFrame) -> pd.DataFrame:
        if raw.empty:
            return raw
        return CommodityPriceSchema.validate(raw)

    def normalize(self, validated: pd.DataFrame) -> list[CommodityPrice]:
        return [
            CommodityPrice(
                time=row.time,
                commodity_id=int(row.commodity_id),
                price_usd_per_mt=row.price_usd_per_mt,
                data_provenance=row.data_provenance,
            )
            for row in validated.itertuples(index=False)
        ]
