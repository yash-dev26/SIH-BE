import os
from datetime import date
from pathlib import Path
from typing import List, Optional
import numpy as np
import pandas as pd


def find_dataset_dir() -> Optional[Path]:
    """Finds the dataset directory containing real BDI, Bunker, and Commodity files."""
    candidate_paths = [
        Path(__file__).resolve().parent.parent.parent.parent / "dataset",
        Path(__file__).resolve().parent.parent.parent / "dataset",
        Path(r"c:\Users\Admin\Documents\freightsystem\dataset"),
    ]
    for p in candidate_paths:
        if p.exists() and (p / "Baltic Dry Index Historical Data (1).xlsx").exists():
            return p
    return None


def load_real_training_panel(
    dataset_dir: Optional[Path] = None,
    lanes: Optional[List[int]] = None,
    classes: Optional[List[int]] = None,
) -> pd.DataFrame:
    """
    Loads real historical dataset from dataset/ (BDI index, VLSFO bunker prices, commodity prices)
    and constructs a feature engineering panel DataFrame across trade lanes and vessel classes.
    """
    if dataset_dir is None:
        dataset_dir = find_dataset_dir()
        if dataset_dir is None:
            raise FileNotFoundError("Dataset directory not found.")

    if lanes is None:
        lanes = list(range(1, 14))
    if classes is None:
        classes = [1, 2, 3, 4]

    bdi_path = dataset_dir / "Baltic Dry Index Historical Data (1).xlsx"
    bunker_path = dataset_dir / "Daily_Bunker_Fuel_Prices_20260914.csv"
    comm_path = dataset_dir / "commodity_prices_monthly_wide.csv"

    # Master daily date range (5+ years of historical data)
    master_dates = pd.date_range(start="2021-01-01", end="2026-12-31", freq="D")
    df_master = pd.DataFrame({"date": master_dates})

    # 1. Load Real Baltic Dry Index (BDI)
    bdi_df = pd.read_excel(bdi_path)
    bdi_df["date"] = pd.to_datetime(bdi_df["Date"], errors="coerce")
    bdi_df["bdi_price"] = pd.to_numeric(bdi_df["Price"], errors="coerce")
    bdi_df = bdi_df.dropna(subset=["date", "bdi_price"])[["date", "bdi_price"]].drop_duplicates(subset=["date"])

    # 2. Load Real Daily VLSFO Bunker Fuel Prices
    bunker_df = pd.read_csv(bunker_path)
    bunker_df["date"] = pd.to_datetime(bunker_df["Day"], errors="coerce")
    bunker_df["vlsfo_price"] = (
        bunker_df["VLSFO Fuel Oil, IMO 2020 Grade, 0.5%"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .astype(float)
    )
    bunker_df = bunker_df.dropna(subset=["date", "vlsfo_price"])[["date", "vlsfo_price"]].drop_duplicates(subset=["date"])

    # 3. Load Real Monthly Commodity Prices
    comm_df = pd.read_csv(comm_path)
    comm_df["date"] = pd.to_datetime(comm_df["Date"], errors="coerce")
    comm_df["thermal_coal_price"] = pd.to_numeric(comm_df["Coal, South African ** ($/mt)"], errors="coerce")
    comm_df["coking_coal_price"] = pd.to_numeric(comm_df["Coal, Australian ($/mt)"], errors="coerce")
    comm_df["iron_ore_price"] = pd.to_numeric(comm_df["Iron ore, cfr spot ($/dmtu)"], errors="coerce")
    comm_df = comm_df.dropna(subset=["date"])[
        ["date", "thermal_coal_price", "coking_coal_price", "iron_ore_price"]
    ].drop_duplicates(subset=["date"])

    # Merge on master dates
    df_grid = pd.merge(df_master, bdi_df, on="date", how="left")
    df_grid = pd.merge(df_grid, bunker_df, on="date", how="left")
    df_grid = pd.merge_asof(df_grid.sort_values("date"), comm_df.sort_values("date"), on="date", direction="backward")

    # Forward/backward fill gaps
    df_grid["bdi_price"] = df_grid["bdi_price"].ffill().bfill().fillna(2000.0)
    df_grid["vlsfo_price"] = df_grid["vlsfo_price"].ffill().bfill().fillna(550.0)
    df_grid["thermal_coal_price"] = df_grid["thermal_coal_price"].ffill().bfill().fillna(130.0)
    df_grid["coking_coal_price"] = df_grid["coking_coal_price"].ffill().bfill().fillna(220.0)
    df_grid["iron_ore_price"] = df_grid["iron_ore_price"].ffill().bfill().fillna(110.0)

    # Baseline multipliers per vessel class (DWT capacity scaling)
    tce_multiplier_per_class = {
        1: 5.2,   # Handysize
        2: 6.8,   # Supramax
        3: 8.5,   # Panamax
        4: 12.0,  # Capesize
    }
    dist_map = {
        1: 6100.0, 2: 6000.0, 3: 6300.0, 4: 6000.0, 5: 10500.0,
        6: 10600.0, 7: 2700.0, 8: 3000.0, 9: 2500.0, 10: 2400.0,
        11: 2350.0, 12: 2600.0, 13: 2500.0
    }

    records = []

    for lane_id in lanes:
        distance = dist_map.get(lane_id, 5200.0)
        transit_days = distance / 300.0

        for class_id in classes:
            mult = tce_multiplier_per_class.get(class_id, 8.5)
            df_lane = df_grid.copy()
            df_lane["trade_lane_id"] = lane_id
            df_lane["vessel_class_id"] = class_id
            df_lane["sea_distance_nm"] = distance
            df_lane["typical_transit_days"] = transit_days

            # Calculate TCE & Spot rate using real Baltic Dry Index & commodity/bunker prices
            time_idx = np.arange(len(df_lane))
            seasonal = 800.0 * np.sin(2 * np.pi * time_idx / 365.25 - 1.2)

            tce_rates = np.maximum(
                5000.0,
                df_lane["bdi_price"] * mult
                + (df_lane["coking_coal_price"] - 200.0) * 8.0
                + (df_lane["vlsfo_price"] - 550.0) * 5.0
                + seasonal
            )
            spot_rates = np.maximum(7.0, (tce_rates / 1000.0) + (distance / 450.0))

            df_lane["TCE_rate"] = tce_rates
            df_lane["spot_rate"] = spot_rates
            df_lane["avg_waiting_days_load"] = np.maximum(1.0, 2.5 + 1.5 * np.sin(2 * np.pi * time_idx / 365.25))
            df_lane["avg_waiting_days_discharge"] = np.maximum(1.0, 3.5 + 2.0 * np.cos(2 * np.pi * time_idx / 365.25))

            df_lane["month"] = df_lane["date"].dt.month
            df_lane["week_of_year"] = df_lane["date"].dt.isocalendar().week.astype(int)
            df_lane["sin_month"] = np.sin(2 * np.pi * df_lane["month"] / 12.0)
            df_lane["cos_month"] = np.cos(2 * np.pi * df_lane["month"] / 12.0)
            df_lane["monsoon_season_flag"] = df_lane["month"].isin([6, 7, 8, 9]).astype(int)
            df_lane["cyclone_season_flag"] = df_lane["month"].isin([10, 11, 12, 4, 5]).astype(int)

            df_lane["rate_lag_1d"] = df_lane["TCE_rate"].shift(1)
            df_lane["rate_lag_7d"] = df_lane["TCE_rate"].shift(7)
            df_lane["rate_lag_30d"] = df_lane["TCE_rate"].shift(30)
            df_lane["rate_lag_90d"] = df_lane["TCE_rate"].shift(90)

            df_lane["rate_rolling_mean_7d"] = df_lane["TCE_rate"].shift(1).rolling(7).mean()
            df_lane["rate_rolling_std_7d"] = df_lane["TCE_rate"].shift(1).rolling(7).std().fillna(0)
            df_lane["rate_rolling_mean_30d"] = df_lane["TCE_rate"].shift(1).rolling(30).mean()
            df_lane["rate_rolling_std_30d"] = df_lane["TCE_rate"].shift(1).rolling(30).std().fillna(0)
            df_lane["vlsfo_price_30d_trend"] = df_lane["vlsfo_price"] - df_lane["vlsfo_price"].shift(30)

            df_lane = df_lane.bfill().ffill()
            records.append(df_lane)

    full_df = pd.concat(records, ignore_index=True)
    return full_df
