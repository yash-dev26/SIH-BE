"""Lag & rolling-window features (Section 3.1: "rate_lag_1d, 7d, 30d, 90d;
rolling mean/std (7/30/90d); rolling min/max").

Operates on a long-format freight_rates DataFrame (one row per
time/trade_lane_id/vessel_class_id/rate_type) and computes lags/rolling
stats independently per (trade_lane_id, vessel_class_id) group so one lane's
history never leaks into another's.
"""

from __future__ import annotations

import pandas as pd

LAG_DAYS = (1, 7, 30, 90)
ROLLING_WINDOWS = (7, 30, 90)
GROUP_COLS = ["trade_lane_id", "vessel_class_id"]


def compute_lag_features(freight_rates_df: pd.DataFrame, *, rate_type: str = "TCE") -> pd.DataFrame:
    """freight_rates_df columns expected: time, trade_lane_id, vessel_class_id,
    rate_type, rate_value. Returns one row per (lane, class, time) for the
    requested rate_type, with lag_* / rolling_* columns appended.
    """
    if freight_rates_df.empty:
        return freight_rates_df

    df = freight_rates_df[freight_rates_df["rate_type"] == rate_type].copy()
    if df.empty:
        return df

    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values(GROUP_COLS + ["time"]).reset_index(drop=True)

    grouped_rate = df.groupby(GROUP_COLS)["rate_value"]

    for lag in LAG_DAYS:
        df[f"rate_lag_{lag}d"] = grouped_rate.shift(lag)

    for window in ROLLING_WINDOWS:
        df[f"rate_rolling_mean_{window}d"] = grouped_rate.transform(
            lambda s, w=window: s.rolling(window=w, min_periods=1).mean()
        )
        df[f"rate_rolling_std_{window}d"] = grouped_rate.transform(
            lambda s, w=window: s.rolling(window=w, min_periods=2).std()
        )
        df[f"rate_rolling_min_{window}d"] = grouped_rate.transform(
            lambda s, w=window: s.rolling(window=w, min_periods=1).min()
        )
        df[f"rate_rolling_max_{window}d"] = grouped_rate.transform(
            lambda s, w=window: s.rolling(window=w, min_periods=1).max()
        )

    return df
