from datetime import date, datetime
import numpy as np
import pandas as pd


def generate_synthetic_training_panel(
    as_of_date: date = None,
    lanes: list[int] = None,
    classes: list[int] = None,
    num_days: int = 1825,  # 5 years
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generates realistic, econometrically correlated time-series feature panel for all
    trade lanes & vessel classes. Preserves realistic relationships between freight TCE rates,
    vessel class sizes, sea distances, bunker costs, and seasonal demand.
    """
    np.random.seed(seed)
    if as_of_date is None:
        as_of_date = date.today()

    if lanes is None:
        lanes = list(range(1, 14))  # All 13 seed trade lanes
    if classes is None:
        classes = [1, 2, 3, 4]  # All 4 vessel classes: Handysize, Supramax, Panamax, Capesize

    end_date = pd.to_datetime(as_of_date)
    start_date = end_date - pd.Timedelta(days=num_days)
    date_range = pd.date_range(start=start_date, end=end_date, freq="D")
    n = len(date_range)
    time_idx = np.arange(n)

    # Base Macro Economic Signals (Shared global factors)
    vlsfo_base = 550.0 + 60.0 * np.sin(2 * np.pi * time_idx / 365.25) + np.random.normal(0, 4.0, n)
    coking_coal_base = 220.0 + 40.0 * np.cos(2 * np.pi * time_idx / 365.25) + np.random.normal(0, 5.0, n)
    thermal_coal_base = 130.0 + 25.0 * np.cos(2 * np.pi * time_idx / 365.25 - 0.5) + np.random.normal(0, 3.0, n)
    iron_ore_base = 110.0 + 20.0 * np.sin(2 * np.pi * time_idx / 180.0) + np.random.normal(0, 2.0, n)

    # Baseline TCE rates per vessel class
    tce_baseline_per_class = {
        1: 9500.0,   # Handysize
        2: 13000.0,  # Supramax
        3: 17500.0,  # Panamax
        4: 25000.0,  # Capesize
    }

    records = []

    for lane_id in lanes:
        # Sea distance baseline (approximated by lane ID if not specified)
        distance = 5200.0 if lane_id in [1, 2, 6, 7] else (2400.0 if lane_id in [8, 9, 12, 13] else 8500.0)
        transit_days = distance / 300.0

        for class_id in classes:
            base_tce = tce_baseline_per_class.get(class_id, 15000.0)
            base_spot = (base_tce / 1000.0) + (distance / 450.0)

            # Auto-regressive (AR1) market sentiment noise
            ar_noise = np.zeros(n)
            phi = 0.88
            scale = 300.0 if class_id == 1 else (450.0 if class_id == 2 else (650.0 if class_id == 3 else 1000.0))
            for i in range(1, n):
                ar_noise[i] = phi * ar_noise[i - 1] + np.random.normal(0, scale)

            # Seasonal demand swings (monsoon dip, Q4 winter surge)
            seasonal = (base_tce * 0.15) * np.sin(2 * np.pi * time_idx / 365.25 - 1.2)
            
            # Port congestion waiting days
            avg_waiting_load = np.maximum(1.0, 2.5 + 1.5 * np.sin(2 * np.pi * time_idx / 365.25) + np.random.normal(0, 0.5, n))
            avg_waiting_disch = np.maximum(1.0, 3.5 + 2.0 * np.cos(2 * np.pi * time_idx / 365.25) + np.random.normal(0, 0.8, n))

            tce_rates = np.maximum(
                base_tce * 0.4,
                base_tce + seasonal + ar_noise + 12.0 * (coking_coal_base - 220.0) + 8.0 * (vlsfo_base - 550.0)
            )
            spot_rates = np.maximum(7.0, base_spot + tce_rates / 1100.0 + np.random.normal(0, 0.4, n))

            df_lane = pd.DataFrame({
                "date": date_range,
                "trade_lane_id": lane_id,
                "vessel_class_id": class_id,
                "TCE_rate": tce_rates,
                "spot_rate": spot_rates,
                "vlsfo_price": vlsfo_base,
                "thermal_coal_price": thermal_coal_base,
                "coking_coal_price": coking_coal_base,
                "iron_ore_price": iron_ore_base,
                "avg_waiting_days_load": avg_waiting_load,
                "avg_waiting_days_discharge": avg_waiting_disch,
                "sea_distance_nm": distance,
                "typical_transit_days": transit_days,
            })

            # Feature Engineering: Lags, Rolling Stats, and Seasonality Encodings
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


