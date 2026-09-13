"""
SyntheticDataGenerator — Section 2.2 of the implementation plan.

Produces statistically plausible historical series for every time-series
table so the MVP is fully demoable with zero paid API keys
(`USE_SYNTHETIC_DATA=true`). Every row this module produces is tagged
`data_provenance='synthetic'` — nothing here is ever meant to be mistaken for
ground truth (Section 2.2, point 4 / Section 5.3's UI-honesty requirement).

Phase 1 note: this generator does NOT yet calibrate against a real BDI proxy
series (Section 2.2, point 1 calls for fitting to the free Trading Economics
series) because the BDI proxy connector doesn't exist until Phase 2. Instead
it uses self-contained seasonal-GBM parameters, keeping the *shape*
(seasonality, volatility clustering, route/class multipliers) plausible
without pretending to be calibrated to a live source. Swap in real
calibration once `bdi_proxy_connector.py` lands.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

# Rough baseline TCE (USD/day) and spot (USD/MT) levels per vessel class,
# order-of-magnitude figures for a coal-carrying dry-bulk market — not a
# citation-backed source, purely to give the synthetic series a believable
# scale. Larger classes command higher USD/day but lower USD/MT (economies
# of scale), which is why the two don't move in the same rank order.
_BASE_TCE_USD_PER_DAY = {
    "Handysize": 9000.0,
    "Supramax": 11000.0,
    "Panamax": 13500.0,
    "Capesize": 17000.0,
}
_BASE_SPOT_USD_PER_MT = {
    "Handysize": 22.0,
    "Supramax": 18.0,
    "Panamax": 14.0,
    "Capesize": 10.0,
}
_BASE_BUNKER_USD_PER_MT = {"VLSFO": 550.0, "IFO380": 420.0, "MGO": 780.0}
_BASE_COMMODITY_USD_PER_MT = {
    "thermal_coal": 110.0,
    "coking_coal": 220.0,
    "iron_ore": 105.0,
}


def _monsoon_flag(d: date) -> bool:
    """Bay of Bengal monsoon window, per Section 3.1's feature catalogue (Jun-Sep)."""
    return d.month in (6, 7, 8, 9)


def _cyclone_season_flag(d: date) -> bool:
    """Bay of Bengal cyclone season: Oct-Dec and Apr-Jun pre-monsoon (Section 3.4)."""
    return d.month in (10, 11, 12, 4, 5, 6)


def _seasonal_multiplier(d: date) -> float:
    """Smooth annual seasonality via a sine wave, peaking around N. Hemisphere
    winter heating-demand season (Section 3.1's seasonality feature group)."""
    day_of_year = d.timetuple().tm_yday
    return 1.0 + 0.08 * math.sin(2 * math.pi * (day_of_year - 335) / 365.25)


@dataclass
class SyntheticDataGenerator:
    years_of_history: int
    random_seed: int
    as_of: date = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.as_of is None:
            self.as_of = date.today()
        self.rng = np.random.default_rng(self.random_seed)

    def _date_range(self) -> pd.DatetimeIndex:
        start = self.as_of - timedelta(days=365 * self.years_of_history)
        return pd.date_range(start=start, end=self.as_of, freq="D", tz=timezone.utc)

    # ------------------------------------------------------------------
    # Freight rates (TCE + SPOT) per trade lane x vessel class
    # ------------------------------------------------------------------
    def generate_freight_rates(self, trade_lanes: list[dict], vessel_classes: list[dict]) -> pd.DataFrame:
        """`trade_lanes`: list of {trade_lane_id, commodity}. `vessel_classes`:
        list of {vessel_class_id, class_name}. Generates both TCE (USD/day) and
        SPOT (USD/MT) daily series for every (lane, class) pair — a full pooled
        panel, matching the Tier-0 LightGBM model's expected input shape
        (Section 3.1)."""
        dates = self._date_range()
        rows = []

        for lane in trade_lanes:
            for vclass in vessel_classes:
                class_name = vclass["class_name"]
                base_tce = _BASE_TCE_USD_PER_DAY[class_name]
                base_spot = _BASE_SPOT_USD_PER_MT[class_name]

                # GBM-with-drift: log-returns ~ N(mu, sigma), small positive
                # drift, plus a shared seasonal multiplier and an idiosyncratic
                # AR(1)-ish volatility-clustering nudge.
                n = len(dates)
                mu, sigma = 0.0002, 0.018
                shocks = self.rng.normal(mu, sigma, size=n)
                log_level = np.cumsum(shocks)
                drift_series = np.exp(log_level - log_level.mean())

                seasonal = np.array([_seasonal_multiplier(d.date()) for d in dates])
                monsoon_bump = np.array(
                    [1.05 if _monsoon_flag(d.date()) else 1.0 for d in dates]
                )

                tce_series = base_tce * drift_series * seasonal * monsoon_bump
                spot_series = base_spot * drift_series * seasonal * monsoon_bump

                for i, d in enumerate(dates):
                    rows.append(
                        {
                            "time": d,
                            "trade_lane_id": lane["trade_lane_id"],
                            "vessel_class_id": vclass["vessel_class_id"],
                            "rate_type": "TCE",
                            "rate_value": round(float(tce_series[i]), 2),
                            "rate_unit": "USD_PER_DAY",
                            "data_provenance": "synthetic",
                            "source": "SyntheticDataGenerator",
                        }
                    )
                    rows.append(
                        {
                            "time": d,
                            "trade_lane_id": lane["trade_lane_id"],
                            "vessel_class_id": vclass["vessel_class_id"],
                            "rate_type": "SPOT",
                            "rate_value": round(float(spot_series[i]), 2),
                            "rate_unit": "USD_PER_MT",
                            "data_provenance": "synthetic",
                            "source": "SyntheticDataGenerator",
                        }
                    )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Bunker prices
    # ------------------------------------------------------------------
    def generate_bunker_prices(self) -> pd.DataFrame:
        dates = self._date_range()
        rows = []
        n = len(dates)
        for grade, base in _BASE_BUNKER_USD_PER_MT.items():
            shocks = self.rng.normal(0.0001, 0.015, size=n)
            level = base * np.exp(np.cumsum(shocks) - np.cumsum(shocks).mean())
            for i, d in enumerate(dates):
                rows.append(
                    {
                        "time": d,
                        "port_id": None,  # NULL = global reference price, per Section 2.3
                        "fuel_grade": grade,
                        "price_usd_per_mt": round(float(level[i]), 2),
                        "data_provenance": "synthetic",
                    }
                )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Commodity prices
    # ------------------------------------------------------------------
    def generate_commodity_prices(self, commodities: list[dict]) -> pd.DataFrame:
        dates = self._date_range()
        rows = []
        n = len(dates)
        for commodity in commodities:
            base = _BASE_COMMODITY_USD_PER_MT.get(commodity["commodity_name"], 100.0)
            shocks = self.rng.normal(0.0001, 0.012, size=n)
            level = base * np.exp(np.cumsum(shocks) - np.cumsum(shocks).mean())
            for i, d in enumerate(dates):
                rows.append(
                    {
                        "time": d,
                        "commodity_id": commodity["commodity_id"],
                        "price_usd_per_mt": round(float(level[i]), 2),
                        "data_provenance": "synthetic",
                    }
                )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Port congestion — Poisson-ish queueing process w/ seasonal spikes
    # ------------------------------------------------------------------
    def generate_port_congestion(self, ports: list[dict]) -> pd.DataFrame:
        dates = self._date_range()
        rows = []
        for port in ports:
            base_wait = 1.5  # days, calm-season baseline
            for d in dates:
                dd = d.date()
                seasonal_bump = 2.5 if _cyclone_season_flag(dd) else 0.0
                lam = max(base_wait + seasonal_bump, 0.1)
                avg_wait = float(self.rng.gamma(shape=2.0, scale=lam / 2.0))
                vessels_waiting = int(self.rng.poisson(lam=max(avg_wait, 0.1)))
                rows.append(
                    {
                        "time": d,
                        "port_id": port["port_id"],
                        "vessels_waiting": vessels_waiting,
                        "avg_waiting_days": round(avg_wait, 2),
                        "data_provenance": "synthetic",
                    }
                )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Tide levels — sinusoidal semi-diurnal approximation (Section 2.2, pt.3)
    # ------------------------------------------------------------------
    def generate_tide_levels(self, ports: list[dict]) -> pd.DataFrame:
        dates = self._date_range()
        rows = []
        for port in ports:
            amplitude = float(port.get("tidal_range_m") or 1.5) / 2.0
            for i, d in enumerate(dates):
                # ~12.4h semi-diurnal period; sampled once/day at a fixed hour,
                # so this captures day-to-day spring/neap variation, not the
                # intra-day cycle. A real INCOIS/NOAA connector (Phase 2)
                # supersedes this at finer granularity.
                phase = 2 * math.pi * (i % 29) / 29  # ~lunar month spring/neap cycle
                tide_height = amplitude * (1 + 0.3 * math.sin(phase)) * math.sin(
                    2 * math.pi * 12 / 24.8
                )
                rows.append(
                    {
                        "time": d,
                        "port_id": port["port_id"],
                        "tide_height_m": round(float(tide_height), 2),
                        "data_provenance": "synthetic",
                    }
                )
        return pd.DataFrame(rows)
