"""Synthetic fallback generator for connectors whose live source is stubbed,
paywalled, or transiently unreachable.

Per Section 5.3's fallback chain: live -> cached last-known-good -> proxy ->
synthetic (explicitly flagged) -> conservative default. This module owns the
"synthetic" tier. Every generator here is deterministic given a seed, so
re-runs are reproducible, and every row it produces carries
`data_provenance="synthetic"` — never anything stronger.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd


class SyntheticDataGenerator:
    def __init__(self, random_seed: int = 42) -> None:
        self._rng = np.random.default_rng(random_seed)

    def _date_range(self, start: date, end: date) -> pd.DatetimeIndex:
        return pd.date_range(start=start, end=end, freq="D", tz=timezone.utc)

    def freight_rates(
        self,
        *,
        trade_lane_ids: list[int],
        vessel_class_id: int,
        start: date,
        end: date,
        rate_type: str = "SPOT",
        rate_unit: str = "USD_PER_MT",
        base_level: float = 22.0,
    ) -> pd.DataFrame:
        """Mean-reverting random walk with mild seasonality, one series per lane."""
        idx = self._date_range(start, end)
        rows = []
        for lane_id in trade_lane_ids:
            level = base_level * self._rng.uniform(0.85, 1.15)
            for t in idx:
                seasonal = 1 + 0.08 * np.sin(2 * np.pi * t.dayofyear / 365.0)
                shock = self._rng.normal(0, 0.02)
                level = max(1.0, level * (1 + shock)) * 0.995 + base_level * 0.005
                rows.append(
                    {
                        "time": t,
                        "trade_lane_id": lane_id,
                        "vessel_class_id": vessel_class_id,
                        "rate_type": rate_type,
                        "rate_value": round(level * seasonal, 2),
                        "rate_unit": rate_unit,
                        "data_provenance": "synthetic",
                        "source": "synthetic_generator",
                    }
                )
        return pd.DataFrame(rows)

    def bunker_prices(
        self, *, port_ids: list[int | None], start: date, end: date, base_price: float = 550.0
    ) -> pd.DataFrame:
        idx = self._date_range(start, end)
        rows = []
        for port_id in port_ids:
            level = base_price * self._rng.uniform(0.9, 1.1)
            for t in idx:
                level = max(50.0, level * (1 + self._rng.normal(0, 0.015)))
                for grade, mult in (("VLSFO", 1.0), ("IFO380", 0.85), ("MGO", 1.25)):
                    rows.append(
                        {
                            "time": t,
                            "port_id": port_id,
                            "fuel_grade": grade,
                            "price_usd_per_mt": round(level * mult, 2),
                            "data_provenance": "synthetic",
                        }
                    )
        return pd.DataFrame(rows)

    def commodity_prices(
        self, *, commodity_ids: list[int], start: date, end: date, base_price: float = 110.0
    ) -> pd.DataFrame:
        idx = self._date_range(start, end)
        rows = []
        for commodity_id in commodity_ids:
            level = base_price * self._rng.uniform(0.8, 1.2)
            for t in idx:
                level = max(5.0, level * (1 + self._rng.normal(0, 0.01)))
                rows.append(
                    {
                        "time": t,
                        "commodity_id": commodity_id,
                        "price_usd_per_mt": round(level, 2),
                        "data_provenance": "synthetic",
                    }
                )
        return pd.DataFrame(rows)

    def port_congestion(
        self, *, port_ids: list[int], start: date, end: date, monsoon_months: tuple[int, ...] = (6, 7, 8, 9)
    ) -> pd.DataFrame:
        idx = self._date_range(start, end)
        rows = []
        for port_id in port_ids:
            for t in idx:
                seasonal_bump = 1.6 if t.month in monsoon_months else 1.0
                waiting = max(0.0, self._rng.gamma(shape=1.5, scale=1.2) * seasonal_bump)
                rows.append(
                    {
                        "time": t,
                        "port_id": port_id,
                        "vessels_waiting": int(self._rng.poisson(3 * seasonal_bump)),
                        "avg_waiting_days": round(waiting, 2),
                        "data_provenance": "synthetic",
                    }
                )
        return pd.DataFrame(rows)

    def tide_levels(self, *, port_ids: list[int], start: date, end: date, tidal_range_m: float = 3.0) -> pd.DataFrame:
        idx = self._date_range(start, end)
        rows = []
        for port_id in port_ids:
            phase = self._rng.uniform(0, 2 * np.pi)
            for i, t in enumerate(idx):
                # Two semi-diurnal-ish cycles per day approximated at daily granularity
                # via a slow lunar-cycle envelope — adequate for MVP synthetic fallback.
                height = (tidal_range_m / 2) * (1 + np.sin(2 * np.pi * i / 14.0 + phase)) / 2
                rows.append(
                    {
                        "time": t,
                        "port_id": port_id,
                        "tide_height_m": round(float(height), 2),
                        "data_provenance": "synthetic",
                    }
                )
        return pd.DataFrame(rows)

    def ais_positions(
        self, *, imo_numbers: list[str], start: date, end: date, anchor_lat: float = 17.0, anchor_lon: float = 83.3
    ) -> pd.DataFrame:
        idx = self._date_range(start, end)
        rows = []
        for imo in imo_numbers:
            lat, lon = anchor_lat + self._rng.uniform(-3, 3), anchor_lon + self._rng.uniform(-3, 3)
            for t in idx:
                lat += self._rng.normal(0, 0.05)
                lon += self._rng.normal(0, 0.05)
                rows.append(
                    {
                        "time": t,
                        "imo_number": imo,
                        "latitude": round(float(lat), 5),
                        "longitude": round(float(lon), 5),
                        "speed_knots": round(max(0.0, self._rng.normal(11, 3)), 2),
                        "heading": round(float(self._rng.uniform(0, 360)), 1),
                        "nav_status": "under_way_using_engine",
                        "data_provenance": "synthetic",
                    }
                )
        return pd.DataFrame(rows)
