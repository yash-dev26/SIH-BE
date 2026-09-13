"""Macro / commodity / bunker features (Section 3.1: "thermal coal price,
coking coal price, iron ore price (lagged 1-4 weeks)" and "VLSFO price
level & 30d trend").

Produces one row per `time` (these are global/lane-agnostic signals) with
wide columns ready to left-join onto the lane×class panel in
build_training_panel.py.
"""

from __future__ import annotations

import pandas as pd

COMMODITY_LAG_WEEKS = (1, 2, 3, 4)


def build_commodity_features(commodity_prices_df: pd.DataFrame, commodity_name_by_id: dict[int, str]) -> pd.DataFrame:
    """commodity_prices_df columns: time, commodity_id, price_usd_per_mt."""
    if commodity_prices_df.empty:
        return pd.DataFrame(columns=["time"])

    df = commodity_prices_df.copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["commodity_name"] = df["commodity_id"].map(commodity_name_by_id)
    df = df.dropna(subset=["commodity_name"])

    wide = df.pivot_table(index="time", columns="commodity_name", values="price_usd_per_mt", aggfunc="last")
    wide = wide.sort_index()

    out = pd.DataFrame(index=wide.index)
    for col in wide.columns:
        out[f"{col}_price"] = wide[col]
        for weeks in COMMODITY_LAG_WEEKS:
            out[f"{col}_price_lag_{weeks}w"] = wide[col].shift(weeks * 7)

    return out.reset_index()


def build_bunker_features(bunker_prices_df: pd.DataFrame, *, fuel_grade: str = "VLSFO") -> pd.DataFrame:
    """bunker_prices_df columns: time, port_id, fuel_grade, price_usd_per_mt.
    Uses the global reference row (port_id is NULL) as the level series."""
    if bunker_prices_df.empty:
        return pd.DataFrame(columns=["time"])

    df = bunker_prices_df[
        (bunker_prices_df["fuel_grade"] == fuel_grade) & (bunker_prices_df["port_id"].isna())
    ].copy()
    if df.empty:
        # Fall back to averaging across whatever ports we do have, rather
        # than returning an empty frame and silently dropping the feature.
        df = bunker_prices_df[bunker_prices_df["fuel_grade"] == fuel_grade].copy()
        df = df.groupby("time", as_index=False)["price_usd_per_mt"].mean()

    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time")

    out = df[["time", "price_usd_per_mt"]].rename(columns={"price_usd_per_mt": f"{fuel_grade.lower()}_price"})
    out[f"{fuel_grade.lower()}_price_trend_30d"] = out[f"{fuel_grade.lower()}_price"].pct_change(periods=30)
    return out


def build_macro_features(
    commodity_prices_df: pd.DataFrame,
    bunker_prices_df: pd.DataFrame,
    commodity_name_by_id: dict[int, str],
) -> pd.DataFrame:
    commodity_feats = build_commodity_features(commodity_prices_df, commodity_name_by_id)
    bunker_feats = build_bunker_features(bunker_prices_df)

    if commodity_feats.empty:
        return bunker_feats
    if bunker_feats.empty:
        return commodity_feats
    return pd.merge(commodity_feats, bunker_feats, on="time", how="outer").sort_values("time")
