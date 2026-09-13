#!/usr/bin/env python
"""
Loads vessel_classes, ports, trade_lanes, and commodities from
backend/seed_data/*.yaml into the database.

Idempotent: safe to re-run — existing rows (matched by natural key) are
updated in place rather than duplicated.

Usage:
    python scripts/seed_reference_data.py
"""

import argparse
import sys
from pathlib import Path

import structlog
import yaml
from geoalchemy2 import WKTElement
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db.models import Commodity, Port, TradeLane, VesselClass  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

logger = structlog.get_logger()
settings = get_settings()


def _load_yaml(filename: str) -> list[dict]:
    path = settings.seed_data_dir / filename
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def seed_vessel_classes(db: Session) -> dict[str, int]:
    records = _load_yaml("vessel_classes.yaml")
    name_to_id: dict[str, int] = {}
    for rec in records:
        existing = db.query(VesselClass).filter_by(class_name=rec["class_name"]).one_or_none()
        if existing:
            for key, value in rec.items():
                setattr(existing, key, value)
            row = existing
        else:
            row = VesselClass(**rec)
            db.add(row)
            db.flush()
        name_to_id[rec["class_name"]] = row.vessel_class_id
    db.commit()
    logger.info("seeded_vessel_classes", count=len(records))
    return name_to_id


def seed_commodities(db: Session) -> dict[str, int]:
    records = _load_yaml("commodities.yaml")
    name_to_id: dict[str, int] = {}
    for rec in records:
        existing = db.query(Commodity).filter_by(commodity_name=rec["commodity_name"]).one_or_none()
        if existing:
            for key, value in rec.items():
                setattr(existing, key, value)
            row = existing
        else:
            row = Commodity(**rec)
            db.add(row)
            db.flush()
        name_to_id[rec["commodity_name"]] = row.commodity_id
    db.commit()
    logger.info("seeded_commodities", count=len(records))
    return name_to_id


def seed_ports(db: Session) -> dict[str, int]:
    records = _load_yaml("ports.yaml")
    code_to_id: dict[str, int] = {}
    for rec in records:
        rec = dict(rec)  # shallow copy — we'll mutate before constructing the ORM row
        lat = rec.pop("latitude")
        lon = rec.pop("longitude")
        source = rec.pop("source", None)
        figures_verified = rec.pop("figures_verified", None)

        notes = rec.get("notes", "") or ""
        if source:
            provenance_tag = (
                f"[source: {source}]"
                if figures_verified
                else f"[source: {source} — NOT independently verified, treat as low-confidence]"
            )
            notes = f"{notes} {provenance_tag}".strip()
        rec["notes"] = notes

        location = WKTElement(f"POINT({lon} {lat})", srid=4326)

        existing = db.query(Port).filter_by(port_code=rec["port_code"]).one_or_none()
        if existing:
            for key, value in rec.items():
                setattr(existing, key, value)
            existing.location = location
            row = existing
        else:
            row = Port(location=location, **rec)
            db.add(row)
            db.flush()
        code_to_id[rec["port_code"]] = row.port_id
    db.commit()
    logger.info("seeded_ports", count=len(records))
    return code_to_id


def seed_trade_lanes(db: Session, port_code_to_id: dict[str, int]) -> None:
    records = _load_yaml("trade_lanes.yaml")
    count = 0
    for rec in records:
        origin_id = port_code_to_id[rec["origin_port_code"]]
        dest_id = port_code_to_id[rec["destination_port_code"]]
        commodity = rec["commodity"]

        existing = (
            db.query(TradeLane)
            .filter_by(origin_port_id=origin_id, destination_port_id=dest_id, commodity=commodity)
            .one_or_none()
        )
        payload = {
            "origin_port_id": origin_id,
            "destination_port_id": dest_id,
            "commodity": commodity,
            "sea_distance_nm": rec.get("sea_distance_nm"),
            "typical_transit_days_laden": rec.get("typical_transit_days_laden"),
        }
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            db.add(TradeLane(**payload))
        count += 1
    db.commit()
    logger.info("seeded_trade_lanes", count=count)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    db = SessionLocal()
    try:
        seed_vessel_classes(db)
        seed_commodities(db)
        port_code_to_id = seed_ports(db)
        seed_trade_lanes(db, port_code_to_id)
    finally:
        db.close()

    logger.info("seed_reference_data_complete")


if __name__ == "__main__":
    main()
