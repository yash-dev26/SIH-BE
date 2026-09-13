#!/usr/bin/env python
"""
Generates and loads 5+ years of synthetic historical data across the
time-series tables, plus a small synthetic operational dataset (vessels,
historical charter contracts, and their voyage simulations) so the stack is
fully demoable with zero paid API keys.

Gated behind `USE_SYNTHETIC_DATA=true` (see app/config.py) — refuses to run
otherwise, since synthetic data should never be an accidental default in an
environment meant to run on live/proxy data.

Idempotent: re-running with the same --years-of-history/--random-seed
deletes and regenerates only rows tagged data_provenance='synthetic' within
the affected date range, so it never touches live/proxy rows ingested by
Phase 2+ connectors.

Usage:
    python scripts/seed_synthetic_data.py --years-of-history 5 --random-seed 42
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import structlog
from geoalchemy2 import WKTElement

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db.models import (  # noqa: E402
    AisPosition,
    BunkerPrice,
    CharterContract,
    Commodity,
    CommodityPrice,
    FreightRate,
    Port,
    PortCongestion,
    TideLevel,
    TradeLane,
    Vessel,
    VesselClass,
    VoyageSimulation,
)
from app.db.session import SessionLocal  # noqa: E402
from scripts.synthetic_data_generator import SyntheticDataGenerator  # noqa: E402

logger = structlog.get_logger()
settings = get_settings()

_SYNTHETIC_VESSELS_PER_CLASS = 4
_SYNTHETIC_HISTORICAL_VOYAGES_PER_LANE_CLASS = 6


def _bulk_upsert_timeseries(db, model, df, pk_columns: list[str]) -> None:
    """Delete-then-insert for synthetic time-series rows, scoped to the
    generated date range, so re-runs are idempotent without clobbering any
    live/proxy rows a real connector may have written for the same period."""
    if df.empty:
        return
    min_time, max_time = df["time"].min(), df["time"].max()
    db.query(model).filter(
        model.time >= min_time.to_pydatetime(),
        model.time <= max_time.to_pydatetime(),
        model.data_provenance == "synthetic",
    ).delete(synchronize_session=False)
    db.bulk_insert_mappings(model, df.to_dict(orient="records"))
    db.commit()
    logger.info("upserted_timeseries", table=model.__tablename__, rows=len(df))


def seed_synthetic_vessels(db, vessel_classes: list[dict], rng: np.random.Generator) -> list[dict]:
    """A small synthetic fleet per class — enough for the `vessels` /
    `ais_positions` tables to be non-empty and for historical contracts below
    to reference a real vessel_id. Real fleet data is a Phase 2+/5.5 concern
    (Section 5.5: MVP recommendations are lane/class-level, not per-IMO)."""
    created = []
    for vclass in vessel_classes:
        for i in range(_SYNTHETIC_VESSELS_PER_CLASS):
            imo = f"9{rng.integers(100000, 999999)}"
            existing = db.query(Vessel).filter_by(imo_number=imo).one_or_none()
            if existing:
                continue
            vessel = Vessel(
                imo_number=imo,
                vessel_name=f"SYN {vclass['class_name'].upper()} {i + 1}",
                vessel_class_id=vclass["vessel_class_id"],
                dwt=int(rng.integers(vclass["dwt_min"], vclass["dwt_max"])),
                loa_m=vclass.get("typical_loa_m"),
                beam_m=vclass.get("typical_beam_m"),
                laden_draft_m=vclass.get("typical_laden_draft_m"),
                flag="Panama",
                build_year=int(rng.integers(2005, 2023)),
            )
            db.add(vessel)
            db.flush()
            created.append(
                {
                    "vessel_id": vessel.vessel_id,
                    "imo_number": vessel.imo_number,
                    "vessel_class_id": vessel.vessel_class_id,
                }
            )
    db.commit()
    logger.info("seeded_synthetic_vessels", count=len(created))
    return created


def seed_synthetic_ais(db, vessels: list[dict], as_of: date, rng: np.random.Generator) -> None:
    """A handful of recent position pings per synthetic vessel — placeholder
    until the real AIS connector (Phase 2, Section 2.1.C) lands."""
    rows = []
    for v in vessels:
        for days_ago in range(5):
            t = as_of - timedelta(days=days_ago)
            lon, lat = float(rng.uniform(60, 120)), float(rng.uniform(-20, 25))
            rows.append(
                {
                    "time": t,
                    "imo_number": v["imo_number"],
                    "location": WKTElement(f"POINT({lon} {lat})", srid=4326),
                    "speed_knots": round(float(rng.uniform(0, 15)), 2),
                    "heading": round(float(rng.uniform(0, 360)), 1),
                    "nav_status": "under way using engine",
                    "data_provenance": "synthetic",
                }
            )
    if rows:
        db.execute(AisPosition.__table__.insert(), rows)
        db.commit()
    logger.info("seeded_synthetic_ais_positions", count=len(rows))


def seed_synthetic_historical_voyages(
    db,
    trade_lanes: list[dict],
    vessel_classes: list[dict],
    vessels: list[dict],
    commodity_id_by_lane: dict[int, int],
    as_of: date,
    rng: np.random.Generator,
) -> None:
    """Historical (status=COMPLETED) charter contracts + their voyage
    simulations, so the MILP/forecasting layers (Phases 3-4) have realistic
    historical outcomes to backtest against, and so `charter_contracts` /
    `voyage_simulations` aren't empty after Phase 1 seeding."""
    vessels_by_class: dict[int, list[dict]] = {}
    for v in vessels:
        vessels_by_class.setdefault(v["vessel_class_id"], []).append(v)

    contract_count = 0
    sim_count = 0
    for lane in trade_lanes:
        for vclass in vessel_classes:
            candidates = vessels_by_class.get(vclass["vessel_class_id"])
            if not candidates:
                continue
            for _ in range(_SYNTHETIC_HISTORICAL_VOYAGES_PER_LANE_CLASS):
                vessel = candidates[rng.integers(0, len(candidates))]
                days_ago = int(rng.integers(30, 365 * 3))
                laycan_start = as_of - timedelta(days=days_ago)
                laycan_end = laycan_start + timedelta(days=7)
                cargo_qty = float(rng.integers(vclass["dwt_min"], vclass["dwt_max"]) * 0.9)
                rate_value = round(float(rng.uniform(8, 25)), 2)

                contract = CharterContract(
                    contract_type="SPOT",
                    vessel_id=vessel["vessel_id"],
                    vessel_class_id=vclass["vessel_class_id"],
                    trade_lane_id=lane["trade_lane_id"],
                    commodity_id=commodity_id_by_lane[lane["trade_lane_id"]],
                    cargo_qty_mt=cargo_qty,
                    laycan_start=laycan_start,
                    laycan_end=laycan_end,
                    fixed_rate_value=rate_value,
                    fixed_rate_unit="USD_PER_MT",
                    num_voyages=1,
                    status="COMPLETED",
                )
                db.add(contract)
                db.flush()
                contract_count += 1

                transit_days = float(lane.get("typical_transit_days_laden") or 15.0)
                laden_days = transit_days
                ballast_days = round(transit_days * float(rng.uniform(0.3, 0.6)), 2)
                port_days_load = round(float(rng.uniform(1.5, 4.0)), 2)
                port_days_discharge = round(float(rng.uniform(1.5, 5.0)), 2)
                idle_days = round(float(rng.uniform(0, 2.0)), 2)
                total_days = round(
                    laden_days + ballast_days + port_days_load + port_days_discharge + idle_days, 2
                )
                bunker_cost = round(total_days * float(rng.uniform(3000, 6000)), 2)
                port_cost = round(float(rng.uniform(20000, 80000)), 2)
                demurrage_cost = round(float(rng.uniform(0, 15000)), 2)
                freight_cost = round(cargo_qty * rate_value, 2)
                total_cost = round(bunker_cost + port_cost + demurrage_cost + freight_cost, 2)

                db.add(
                    VoyageSimulation(
                        contract_id=contract.contract_id,
                        trade_lane_id=lane["trade_lane_id"],
                        vessel_class_id=vclass["vessel_class_id"],
                        laden_days=laden_days,
                        ballast_days=ballast_days,
                        port_days_load=port_days_load,
                        port_days_discharge=port_days_discharge,
                        idle_days=idle_days,
                        total_voyage_days=total_days,
                        bunker_cost_usd=bunker_cost,
                        port_cost_usd=port_cost,
                        demurrage_cost_usd=demurrage_cost,
                        freight_cost_usd=freight_cost,
                        total_cost_usd=total_cost,
                        scenario_label="historical_spot",
                    )
                )
                sim_count += 1
    db.commit()
    logger.info("seeded_synthetic_historical_voyages", contracts=contract_count, simulations=sim_count)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years-of-history", type=int, default=5)
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()

    if not settings.use_synthetic_data:
        logger.error(
            "refusing_to_run",
            reason="USE_SYNTHETIC_DATA is false — set it true to intentionally seed synthetic data.",
        )
        sys.exit(1)

    rng = np.random.default_rng(args.random_seed)
    as_of = date.today()
    generator = SyntheticDataGenerator(
        years_of_history=args.years_of_history, random_seed=args.random_seed, as_of=as_of
    )

    db = SessionLocal()
    try:
        vessel_classes = [
            {
                "vessel_class_id": vc.vessel_class_id,
                "class_name": vc.class_name,
                "dwt_min": vc.dwt_min,
                "dwt_max": vc.dwt_max,
                "typical_loa_m": vc.typical_loa_m,
                "typical_beam_m": vc.typical_beam_m,
                "typical_laden_draft_m": vc.typical_laden_draft_m,
            }
            for vc in db.query(VesselClass).all()
        ]
        ports = [
            {"port_id": p.port_id, "tidal_range_m": p.tidal_range_m} for p in db.query(Port).all()
        ]
        trade_lanes_orm = db.query(TradeLane).all()
        trade_lanes = [
            {
                "trade_lane_id": tl.trade_lane_id,
                "commodity": tl.commodity,
                "typical_transit_days_laden": tl.typical_transit_days_laden,
            }
            for tl in trade_lanes_orm
        ]
        commodities = [
            {"commodity_id": c.commodity_id, "commodity_name": c.commodity_name}
            for c in db.query(Commodity).all()
        ]
        commodity_id_by_name = {c["commodity_name"]: c["commodity_id"] for c in commodities}
        commodity_id_by_lane = {
            tl.trade_lane_id: commodity_id_by_name.get(tl.commodity, commodities[0]["commodity_id"])
            for tl in trade_lanes_orm
        }

        if not (vessel_classes and ports and trade_lanes and commodities):
            logger.error(
                "reference_data_missing",
                hint="Run scripts/seed_reference_data.py first.",
            )
            sys.exit(1)

        # --- Time-series ---
        _bulk_upsert_timeseries(
            db, FreightRate, generator.generate_freight_rates(trade_lanes, vessel_classes),
            ["time", "trade_lane_id", "vessel_class_id", "rate_type"],
        )
        _bulk_upsert_timeseries(
            db, BunkerPrice, generator.generate_bunker_prices(), ["time", "fuel_grade", "port_id"]
        )
        _bulk_upsert_timeseries(
            db, CommodityPrice, generator.generate_commodity_prices(commodities),
            ["time", "commodity_id"],
        )
        _bulk_upsert_timeseries(
            db, PortCongestion, generator.generate_port_congestion(ports), ["time", "port_id"]
        )
        _bulk_upsert_timeseries(
            db, TideLevel, generator.generate_tide_levels(ports), ["time", "port_id"]
        )

        # --- Operational / transactional synthetic data ---
        vessels = seed_synthetic_vessels(db, vessel_classes, rng)
        seed_synthetic_ais(db, vessels, as_of, rng)
        seed_synthetic_historical_voyages(
            db, trade_lanes, vessel_classes, vessels, commodity_id_by_lane, as_of, rng
        )
    finally:
        db.close()

    logger.info("seed_synthetic_data_complete", years_of_history=args.years_of_history)


if __name__ == "__main__":
    main()
