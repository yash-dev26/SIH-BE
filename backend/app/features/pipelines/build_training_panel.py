"""build_training_panel.get_training_panel() — the feature/model contract
boundary between Phase 2 (this file) and Phase 3 (model training).

Per Phase 2 task 3:
    "must produce a single reproducible function
    get_training_panel(as_of_date, lanes=None, classes=None) -> pd.DataFrame
    that the model training step (Phase 3) consumes."

Joins: lag features + seasonality + macro (commodity/bunker) + route-static
(sea_distance_nm, typical_transit_days) + port congestion (load & discharge,
lagged) into one wide panel indexed by (trade_lane_id, vessel_class_id, date).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Commodity, CommodityPrice, TradeLane, BunkerPrice, PortCongestion, FreightRate
from app.features.pipelines.lag_features import compute_lag_features
from app.features.pipelines.macro_features import build_macro_features
from app.features.pipelines.seasonality_features import add_seasonality_features

CONGESTION_LAG_DAYS = 7  # "avg_waiting_days at both load & discharge port (lagged)"


def _load_freight_rates(session: Session, as_of: date, lanes, classes) -> pd.DataFrame:
    stmt = select(
        FreightRate.time,
        FreightRate.trade_lane_id,
        FreightRate.vessel_class_id,
        FreightRate.rate_type,
        FreightRate.rate_value,
        FreightRate.rate_unit,
    ).where(FreightRate.time <= datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc))
    if lanes:
        stmt = stmt.where(FreightRate.trade_lane_id.in_(lanes))
    if classes:
        stmt = stmt.where(FreightRate.vessel_class_id.in_(classes))
    rows = session.execute(stmt).all()
    return pd.DataFrame(rows, columns=["time", "trade_lane_id", "vessel_class_id", "rate_type", "rate_value", "rate_unit"])


def _load_commodity_prices(session: Session, as_of: date) -> tuple[pd.DataFrame, dict[int, str]]:
    name_rows = session.execute(select(Commodity.commodity_id, Commodity.commodity_name)).all()
    name_by_id = dict(name_rows)
    stmt = select(
        CommodityPrice.time, CommodityPrice.commodity_id, CommodityPrice.price_usd_per_mt
    ).where(CommodityPrice.time <= datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc))
    rows = session.execute(stmt).all()
    df = pd.DataFrame(rows, columns=["time", "commodity_id", "price_usd_per_mt"])
    return df, name_by_id


def _load_bunker_prices(session: Session, as_of: date) -> pd.DataFrame:
    stmt = select(
        BunkerPrice.time, BunkerPrice.port_id, BunkerPrice.fuel_grade, BunkerPrice.price_usd_per_mt
    ).where(BunkerPrice.time <= datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc))
    rows = session.execute(stmt).all()
    return pd.DataFrame(rows, columns=["time", "port_id", "fuel_grade", "price_usd_per_mt"])


def _load_lane_static(session: Session, lanes) -> pd.DataFrame:
    stmt = select(
        TradeLane.trade_lane_id,
        TradeLane.origin_port_id,
        TradeLane.destination_port_id,
        TradeLane.sea_distance_nm,
        TradeLane.typical_transit_days_laden,
    )
    if lanes:
        stmt = stmt.where(TradeLane.trade_lane_id.in_(lanes))
    rows = session.execute(stmt).all()
    return pd.DataFrame(
        rows,
        columns=["trade_lane_id", "origin_port_id", "destination_port_id", "sea_distance_nm", "typical_transit_days_laden"],
    )


def _load_port_congestion(session: Session, as_of: date) -> pd.DataFrame:
    stmt = select(
        PortCongestion.time, PortCongestion.port_id, PortCongestion.avg_waiting_days
    ).where(PortCongestion.time <= datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc))
    rows = session.execute(stmt).all()
    return pd.DataFrame(rows, columns=["time", "port_id", "avg_waiting_days"])


def _attach_congestion(panel: pd.DataFrame, lane_static: pd.DataFrame, congestion: pd.DataFrame) -> pd.DataFrame:
    if panel.empty or congestion.empty:
        panel["load_port_congestion_lag7d"] = pd.NA
        panel["discharge_port_congestion_lag7d"] = pd.NA
        return panel

    congestion = congestion.copy()
    congestion["time"] = pd.to_datetime(congestion["time"], utc=True)
    congestion = congestion.sort_values(["port_id", "time"])
    congestion["avg_waiting_days_lag7d"] = congestion.groupby("port_id")["avg_waiting_days"].shift(CONGESTION_LAG_DAYS)

    panel = panel.merge(
        lane_static[["trade_lane_id", "origin_port_id", "destination_port_id"]], on="trade_lane_id", how="left"
    )

    for role, port_col in (("load", "origin_port_id"), ("discharge", "destination_port_id")):
        merged = panel.merge(
            congestion[["time", "port_id", "avg_waiting_days_lag7d"]],
            left_on=["time", port_col],
            right_on=["time", "port_id"],
            how="left",
        )
        panel[f"{role}_port_congestion_lag7d"] = merged["avg_waiting_days_lag7d"]

    return panel


def get_training_panel(
    as_of_date: date,
    lanes: list[int] | None = None,
    classes: list[int] | None = None,
    *,
    session_factory=None,
    rate_type: str = "TCE",
) -> pd.DataFrame:
    """The Phase 2 <-> Phase 3 contract. Returns one row per
    (trade_lane_id, vessel_class_id, time) with every Section 3.1 feature
    group joined in. Deterministic for a given as_of_date/lanes/classes
    against a fixed underlying dataset — no randomness introduced here.
    """
    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal

    session = session_factory()
    try:
        freight_df = _load_freight_rates(session, as_of_date, lanes, classes)
        commodity_df, commodity_name_by_id = _load_commodity_prices(session, as_of_date)
        bunker_df = _load_bunker_prices(session, as_of_date)
        lane_static_df = _load_lane_static(session, lanes)
        congestion_df = _load_port_congestion(session, as_of_date)
    finally:
        session.close()

    panel = compute_lag_features(freight_df, rate_type=rate_type)
    if panel.empty:
        # Still return a well-formed, empty-but-correctly-columned frame so
        # callers (Phase 3 training code) don't need a special empty-case
        # branch — an empty panel is a valid, if unhelpful, training input.
        return panel

    panel = add_seasonality_features(panel)

    macro_df = build_macro_features(commodity_df, bunker_df, commodity_name_by_id)
    if not macro_df.empty:
        panel["time"] = pd.to_datetime(panel["time"], utc=True)
        macro_df["time"] = pd.to_datetime(macro_df["time"], utc=True)
        panel = panel.merge(macro_df, on="time", how="left")

    if not lane_static_df.empty:
        panel = panel.merge(
            lane_static_df[["trade_lane_id", "sea_distance_nm", "typical_transit_days_laden"]],
            on="trade_lane_id",
            how="left",
        )

    panel = _attach_congestion(panel, lane_static_df, congestion_df)

    return panel.sort_values(["trade_lane_id", "vessel_class_id", "time"]).reset_index(drop=True)
