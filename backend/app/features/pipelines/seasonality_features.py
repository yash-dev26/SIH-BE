"""Seasonality / calendar features (Section 3.1: "month, week-of-year,
cyclical encodings (sin/cos), monsoon-season flag (Jun-Sep ECI), Chinese
New Year demand-dip flag, N. Hemisphere winter heating-demand flag").

Chinese New Year shifts each year (Jan 21 - Feb 20 window) — rather than a
hardcoded lookup table that goes stale, this uses the well-known date range
that always contains it as a coarse but maintenance-free proxy flag,
clearly documented as an approximation. A precise per-year CNY date table
is a reasonable fast-follow if backtests show the coarse flag underperforms.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MONSOON_MONTHS = {6, 7, 8, 9}  # Jun-Sep, East Coast India
WINTER_HEATING_MONTHS = {11, 12, 1, 2}  # N. Hemisphere winter demand
CNY_WINDOW_MONTH_DAY = ((1, 21), (2, 20))  # approximate CNY window, see module docstring


def _in_cny_window(ts: pd.Timestamp) -> bool:
    start_m, start_d = CNY_WINDOW_MONTH_DAY[0]
    end_m, end_d = CNY_WINDOW_MONTH_DAY[1]
    month_day = (ts.month, ts.day)
    return (start_m, start_d) <= month_day <= (end_m, end_d)


def add_seasonality_features(df: pd.DataFrame, *, time_col: str = "time") -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    ts = pd.to_datetime(out[time_col], utc=True)

    out["month"] = ts.dt.month
    out["week_of_year"] = ts.dt.isocalendar().week.astype(int)

    doy = ts.dt.dayofyear.astype(float)
    days_in_year = ts.dt.is_leap_year.map({True: 366.0, False: 365.0})
    out["doy_sin"] = np.sin(2 * np.pi * doy / days_in_year)
    out["doy_cos"] = np.cos(2 * np.pi * doy / days_in_year)

    out["monsoon_season_flag"] = out["month"].isin(MONSOON_MONTHS).astype(int)
    out["winter_heating_demand_flag"] = out["month"].isin(WINTER_HEATING_MONTHS).astype(int)
    out["chinese_new_year_flag"] = ts.map(_in_cny_window).astype(int)

    # Bay of Bengal cyclone season, used by the Section 3.4 WEATHER_RISK
    # flag and useful as a training feature too (Oct-Dec + Apr-Jun windows).
    out["cyclone_season_flag"] = out["month"].isin({10, 11, 12, 4, 5, 6}).astype(int)

    return out
