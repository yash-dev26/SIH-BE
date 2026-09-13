"""Pandera schemas for each raw ingestion series (Phase 2 task 4).

Design note: connectors resolve foreign keys (port_id, trade_lane_id,
vessel_class_id, commodity_id) during fetch() — since fetch() already has a
DB session available via the connector's ReferenceDataLookup, and several
sources (e.g. the BDI proxy, which isn't itself lane-specific) need to
broadcast a single series across resolved lane IDs before there's anything
meaningful to validate row-by-row. So validate() here operates on
already-FK-resolved DataFrames, immediately before normalize() turns rows
into ORM objects.

Every schema enforces, per Phase 2 task 4:
  - correct dtypes
  - positive / plausible-range values
  - no null keys
  - no future-dated rows
  - no duplicate primary-key tuples
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pandera as pa
from pandera.typing import Series

ALLOWED_RATE_TYPES = {"SPOT", "TCE", "COA", "PERIOD"}
ALLOWED_RATE_UNITS = {"USD_PER_MT", "USD_PER_DAY"}
ALLOWED_PROVENANCE = {"live", "proxy", "synthetic"}
ALLOWED_FUEL_GRADES = {"VLSFO", "IFO380", "MGO"}

# BDI-proxy plausible bounds per Section 2.1 ("clearly label as proxy") /
# Phase 2 task 4 example bounds.
BDI_PROXY_MIN = 200.0
BDI_PROXY_MAX = 20000.0


def _no_future_dates(df: pd.DataFrame, time_col: str = "time") -> bool:
    now = pd.Timestamp.now(tz=timezone.utc)
    return bool((pd.to_datetime(df[time_col], utc=True) <= now).all())


class FreightRateSchema(pa.DataFrameModel):
    time: Series[pd.Timestamp] = pa.Field(nullable=False, coerce=True)
    trade_lane_id: Series[int] = pa.Field(nullable=False, ge=1)
    vessel_class_id: Series[int] = pa.Field(nullable=False, ge=1)
    rate_type: Series[str] = pa.Field(nullable=False, isin=ALLOWED_RATE_TYPES)
    rate_value: Series[float] = pa.Field(nullable=False, gt=0)
    rate_unit: Series[str] = pa.Field(nullable=False, isin=ALLOWED_RATE_UNITS)
    data_provenance: Series[str] = pa.Field(nullable=False, isin=ALLOWED_PROVENANCE)
    source: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = False
        coerce = True

    @pa.dataframe_check
    def no_future_dates(cls, df: pd.DataFrame) -> bool:
        return _no_future_dates(df)

    @pa.dataframe_check
    def no_duplicate_keys(cls, df: pd.DataFrame) -> bool:
        key = ["time", "trade_lane_id", "vessel_class_id", "rate_type"]
        return not df.duplicated(subset=key).any()

    @pa.dataframe_check
    def bdi_proxy_within_bounds(cls, df: pd.DataFrame) -> bool:
        proxy_rows = df[df["data_provenance"] == "proxy"]
        if proxy_rows.empty:
            return True
        return bool(proxy_rows["rate_value"].between(BDI_PROXY_MIN, BDI_PROXY_MAX).all())


class BunkerPriceSchema(pa.DataFrameModel):
    time: Series[pd.Timestamp] = pa.Field(nullable=False, coerce=True)
    port_id: Series[float] = pa.Field(nullable=True)  # nullable FK: NaN allowed for global reference price
    fuel_grade: Series[str] = pa.Field(nullable=False, isin=ALLOWED_FUEL_GRADES)
    price_usd_per_mt: Series[float] = pa.Field(nullable=False, gt=0, le=5000)
    data_provenance: Series[str] = pa.Field(nullable=False, isin=ALLOWED_PROVENANCE)

    class Config:
        strict = False
        coerce = True

    @pa.dataframe_check
    def no_future_dates(cls, df: pd.DataFrame) -> bool:
        return _no_future_dates(df)

    @pa.dataframe_check
    def no_duplicate_keys(cls, df: pd.DataFrame) -> bool:
        key = ["time", "port_id", "fuel_grade"]
        return not df.duplicated(subset=key).any()


class CommodityPriceSchema(pa.DataFrameModel):
    time: Series[pd.Timestamp] = pa.Field(nullable=False, coerce=True)
    commodity_id: Series[int] = pa.Field(nullable=False, ge=1)
    price_usd_per_mt: Series[float] = pa.Field(nullable=False, gt=0)
    data_provenance: Series[str] = pa.Field(nullable=False, isin=ALLOWED_PROVENANCE)

    class Config:
        strict = False
        coerce = True

    @pa.dataframe_check
    def no_future_dates(cls, df: pd.DataFrame) -> bool:
        return _no_future_dates(df)

    @pa.dataframe_check
    def no_duplicate_keys(cls, df: pd.DataFrame) -> bool:
        key = ["time", "commodity_id"]
        return not df.duplicated(subset=key).any()


class PortCongestionSchema(pa.DataFrameModel):
    time: Series[pd.Timestamp] = pa.Field(nullable=False, coerce=True)
    port_id: Series[int] = pa.Field(nullable=False, ge=1)
    vessels_waiting: Series[float] = pa.Field(nullable=True, ge=0)
    avg_waiting_days: Series[float] = pa.Field(nullable=True, ge=0, le=60)
    data_provenance: Series[str] = pa.Field(nullable=False, isin=ALLOWED_PROVENANCE)

    class Config:
        strict = False
        coerce = True

    @pa.dataframe_check
    def no_future_dates(cls, df: pd.DataFrame) -> bool:
        return _no_future_dates(df)

    @pa.dataframe_check
    def no_duplicate_keys(cls, df: pd.DataFrame) -> bool:
        key = ["time", "port_id"]
        return not df.duplicated(subset=key).any()


class TideLevelSchema(pa.DataFrameModel):
    time: Series[pd.Timestamp] = pa.Field(nullable=False, coerce=True)
    port_id: Series[int] = pa.Field(nullable=False, ge=1)
    tide_height_m: Series[float] = pa.Field(nullable=True, ge=-2, le=15)
    data_provenance: Series[str] = pa.Field(nullable=False, isin=ALLOWED_PROVENANCE)

    class Config:
        strict = False
        coerce = True

    @pa.dataframe_check
    def no_future_dates(cls, df: pd.DataFrame) -> bool:
        return _no_future_dates(df)

    @pa.dataframe_check
    def no_duplicate_keys(cls, df: pd.DataFrame) -> bool:
        key = ["time", "port_id"]
        return not df.duplicated(subset=key).any()


class AisPositionSchema(pa.DataFrameModel):
    time: Series[pd.Timestamp] = pa.Field(nullable=False, coerce=True)
    imo_number: Series[str] = pa.Field(nullable=False, str_length={"min_value": 7, "max_value": 15})
    latitude: Series[float] = pa.Field(nullable=False, ge=-90, le=90)
    longitude: Series[float] = pa.Field(nullable=False, ge=-180, le=180)
    speed_knots: Series[float] = pa.Field(nullable=True, ge=0, le=40)
    heading: Series[float] = pa.Field(nullable=True, ge=0, le=360)
    nav_status: Series[str] = pa.Field(nullable=True)
    data_provenance: Series[str] = pa.Field(nullable=False, isin=ALLOWED_PROVENANCE)

    class Config:
        strict = False
        coerce = True

    @pa.dataframe_check
    def no_future_dates(cls, df: pd.DataFrame) -> bool:
        return _no_future_dates(df)

    @pa.dataframe_check
    def no_duplicate_keys(cls, df: pd.DataFrame) -> bool:
        key = ["time", "imo_number"]
        return not df.duplicated(subset=key).any()
