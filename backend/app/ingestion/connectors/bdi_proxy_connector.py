"""Baltic Exchange composite index proxy connector.

Real Baltic Exchange granular data (BDI/BCI/BPI/BSI/BHSI) is a paid
subscription (Section 2.1.A). MVP substitutes the freely-republished daily
headline index values (Trading Economics / Investing.com), explicitly
tagged `data_provenance="proxy"` — never presented as licensed Baltic
Exchange data.

Design note (index -> lane/class mapping): the composite indices are not
lane-specific, but freight_rates requires a NOT NULL trade_lane_id and
vessel_class_id. Each sub-index maps to one vessel class and is broadcast
across every currently-seeded trade lane for that class:

    BCI -> Capesize   BPI -> Panamax   BSI -> Supramax   BHSI -> Handysize

This is a pragmatic MVP choice, not a claim that the index literally prices
each lane — the resulting rows are tagged `source="trading_economics_proxy"`
so downstream consumers (feature pipeline, dashboard) can weight/caveat them
accordingly.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.db.models import FreightRate
from app.ingestion.base_connector import BaseSourceConnector
from app.ingestion.exceptions import SourceUnavailableError
from app.ingestion.lookups import ReferenceDataLookup
from app.ingestion.synthetic import SyntheticDataGenerator
from app.ingestion.validation.expectations import FreightRateSchema

INDEX_TO_CLASS = {
    "BCI": "Capesize",
    "BPI": "Panamax",
    "BSI": "Supramax",
    "BHSI": "Handysize",
}


class BdiProxyConnector(BaseSourceConnector):
    name = "bdi_proxy_connector"
    default_provenance = "proxy"

    def fetch(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)

        if not settings.trading_economics_api_key:
            raise SourceUnavailableError(
                self.name, "TRADING_ECONOMICS_API_KEY not configured", series="BDI_COMPOSITE"
            )

        try:
            raw_by_index = self._fetch_trading_economics(start, as_of)
        except Exception as exc:  # network error, HTML/schema change, rate limit, etc.
            raise SourceUnavailableError(self.name, str(exc), series="BDI_COMPOSITE") from exc

        session = self._session_factory()
        try:
            lookup = ReferenceDataLookup(session)
            frames = []
            for index_name, series in raw_by_index.items():
                class_name = INDEX_TO_CLASS.get(index_name)
                if class_name is None:
                    continue
                vessel_class_id = lookup.vessel_class_id(class_name)
                if vessel_class_id is None:
                    continue
                lanes = [
                    lane_id
                    for (_, _, _, lane_id) in lookup.all_trade_lanes_for_class_hint()
                ]
                for lane_id in lanes:
                    for ts, value in series.items():
                        frames.append(
                            {
                                "time": ts,
                                "trade_lane_id": lane_id,
                                "vessel_class_id": vessel_class_id,
                                "rate_type": "SPOT",
                                "rate_value": float(value),
                                "rate_unit": "USD_PER_DAY",
                                "data_provenance": "proxy",
                                "source": "trading_economics_proxy",
                            }
                        )
        finally:
            session.close()

        return pd.DataFrame(frames)

    def _fetch_trading_economics(self, start: date, end: date) -> dict[str, pd.Series]:
        """Placeholder for the real Trading Economics call.

        Kept as a narrow, isolated method so it's the only thing to swap out
        or mock in tests. Intentionally raises until wired to a real
        (network-restricted in this environment) API client — the
        orchestrator in run() catches this via SourceUnavailableError and
        falls through to the synthetic tier, which is the expected MVP path
        whenever TRADING_ECONOMICS_API_KEY is absent or the call fails.
        """
        raise NotImplementedError(
            "Wire this to the Trading Economics client. Left unimplemented so "
            "CI/local runs deterministically exercise the synthetic fallback "
            "path rather than making a live network call from this method."
        )

    def fallback(self, *, as_of: date | None = None, lookback_days: int = 1, **_) -> pd.DataFrame:
        as_of = as_of or date.today()
        start = as_of - timedelta(days=lookback_days)
        gen = SyntheticDataGenerator(random_seed=settings.random_seed if hasattr(settings, "random_seed") else 42)

        session = self._session_factory()
        try:
            lookup = ReferenceDataLookup(session)
            frames = []
            base_levels = {"Capesize": 18000.0, "Panamax": 13000.0, "Supramax": 11000.0, "Handysize": 9000.0}
            for class_name, base in base_levels.items():
                vessel_class_id = lookup.vessel_class_id(class_name)
                if vessel_class_id is None:
                    continue
                lanes = [lane_id for (_, _, _, lane_id) in lookup.all_trade_lanes_for_class_hint()]
                df = gen.freight_rates(
                    trade_lane_ids=lanes,
                    vessel_class_id=vessel_class_id,
                    start=start,
                    end=as_of,
                    rate_type="SPOT",
                    rate_unit="USD_PER_DAY",
                    base_level=base,
                )
                # synthetic tier: keep provenance/source consistent with the tier
                frames.append(df)
        finally:
            session.close()
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def validate(self, raw: pd.DataFrame) -> pd.DataFrame:
        if raw.empty:
            return raw
        return FreightRateSchema.validate(raw)

    def normalize(self, validated: pd.DataFrame) -> list[FreightRate]:
        return [
            FreightRate(
                time=row.time,
                trade_lane_id=int(row.trade_lane_id),
                vessel_class_id=int(row.vessel_class_id),
                rate_type=row.rate_type,
                rate_value=row.rate_value,
                rate_unit=row.rate_unit,
                data_provenance=row.data_provenance,
                source=getattr(row, "source", None),
            )
            for row in validated.itertuples(index=False)
        ]
