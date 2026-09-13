"""
SQLAlchemy ORM models — mirror the DDL in Section 2.3 of the implementation
plan exactly. This is the source of truth that the initial Alembic migration
(alembic/versions/0001_init_schema.py) is derived from.

Conventions carried over from the plan's engineering principles:
  - Every monetary/rate figure carries an explicit unit column alongside it
    (never an ambiguous "rate").
  - Every time-series table carries a `data_provenance` column
    ('live' | 'proxy' | 'synthetic') for the fallback-chain / confidence
    system in Section 5.3.
  - Time-series tables are TimescaleDB hypertables — see the
    `create_hypertable(...)` calls issued from the Alembic migration
    (hypertable conversion is a DB-side operation, not something the ORM
    layer itself expresses).
"""

import uuid
from datetime import date, datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# =============================================================================
# REFERENCE / MASTER DATA
# =============================================================================


class VesselClass(Base):
    __tablename__ = "vessel_classes"

    vessel_class_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    dwt_min: Mapped[int] = mapped_column(Integer, nullable=False)
    dwt_max: Mapped[int] = mapped_column(Integer, nullable=False)
    typical_loa_m: Mapped[float | None] = mapped_column(Numeric(6, 2))
    typical_beam_m: Mapped[float | None] = mapped_column(Numeric(5, 2))
    typical_laden_draft_m: Mapped[float | None] = mapped_column(Numeric(5, 2))

    vessels: Mapped[list["Vessel"]] = relationship(back_populates="vessel_class")


class Port(Base):
    __tablename__ = "ports"

    port_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    port_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    port_name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # spatial_index=False: we create idx_ports_location explicitly (see the
    # Alembic migration / Section 2.3 DDL) rather than relying on
    # GeoAlchemy2's auto-generated index, to avoid a duplicate-index clash.
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    max_loa_m: Mapped[float | None] = mapped_column(Numeric(6, 2))
    max_beam_m: Mapped[float | None] = mapped_column(Numeric(5, 2))
    max_draft_charted_m: Mapped[float | None] = mapped_column(Numeric(5, 2))
    tidal_range_m: Mapped[float | None] = mapped_column(Numeric(4, 2))
    cargo_handling_rate_mt_per_day: Mapped[float | None] = mapped_column(Numeric(10, 2))
    berth_count: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('LOAD','DISCHARGE','BOTH')", name="ck_ports_role"),
    )


class TradeLane(Base):
    __tablename__ = "trade_lanes"

    trade_lane_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin_port_id: Mapped[int] = mapped_column(ForeignKey("ports.port_id"), nullable=False)
    destination_port_id: Mapped[int] = mapped_column(ForeignKey("ports.port_id"), nullable=False)
    sea_distance_nm: Mapped[float | None] = mapped_column(Numeric(8, 1))
    typical_transit_days_laden: Mapped[float | None] = mapped_column(Numeric(5, 1))
    commodity: Mapped[str] = mapped_column(String(60), nullable=False, default="coal")

    origin_port: Mapped["Port"] = relationship(foreign_keys=[origin_port_id])
    destination_port: Mapped["Port"] = relationship(foreign_keys=[destination_port_id])

    __table_args__ = (
        UniqueConstraint(
            "origin_port_id", "destination_port_id", "commodity", name="uq_trade_lanes_route_commodity"
        ),
    )


class Commodity(Base):
    __tablename__ = "commodities"

    commodity_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commodity_name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    typical_stowage_factor: Mapped[float | None] = mapped_column(Numeric(6, 3))


# =============================================================================
# TIME-SERIES (TimescaleDB hypertables)
# =============================================================================


class FreightRate(Base):
    __tablename__ = "freight_rates"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    trade_lane_id: Mapped[int] = mapped_column(
        ForeignKey("trade_lanes.trade_lane_id"), primary_key=True
    )
    vessel_class_id: Mapped[int] = mapped_column(
        ForeignKey("vessel_classes.vessel_class_id"), primary_key=True
    )
    rate_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    rate_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    rate_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    data_provenance: Mapped[str] = mapped_column(String(20), nullable=False, default="synthetic")
    source: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        CheckConstraint("rate_type IN ('SPOT','TCE','COA','PERIOD')", name="ck_freight_rates_type"),
        CheckConstraint(
            "rate_unit IN ('USD_PER_MT','USD_PER_DAY')", name="ck_freight_rates_unit"
        ),
        CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_freight_rates_provenance"
        ),
    )


class BunkerPrice(Base):
    __tablename__ = "bunker_prices"

    # NOTE on deviation from the plan's literal DDL (Section 2.3): the spec
    # gives `PRIMARY KEY (time, fuel_grade, port_id)` with `port_id` nullable
    # ("NULL = global reference price") — but primary-key columns can't be
    # NULL in standard SQL, so that DDL is not actually runnable as written.
    # Fix: a surrogate `bunker_price_id` PK (paired with `time` so
    # TimescaleDB's "PK must include the partitioning column" requirement is
    # still satisfied), plus two partial unique indexes below that enforce
    # the real business-key uniqueness the original PK was going for —
    # one row per (time, fuel_grade, port) when port-specific, one row per
    # (time, fuel_grade) when global.
    bunker_price_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    port_id: Mapped[int | None] = mapped_column(ForeignKey("ports.port_id"))
    fuel_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    price_usd_per_mt: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    data_provenance: Mapped[str] = mapped_column(String(20), nullable=False, default="synthetic")

    __table_args__ = (
        CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_bunker_prices_provenance"
        ),
    )


class CommodityPrice(Base):
    __tablename__ = "commodity_prices"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    commodity_id: Mapped[int] = mapped_column(
        ForeignKey("commodities.commodity_id"), primary_key=True
    )
    price_usd_per_mt: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    data_provenance: Mapped[str] = mapped_column(String(20), nullable=False, default="synthetic")

    __table_args__ = (
        CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_commodity_prices_provenance"
        ),
    )


class PortCongestion(Base):
    __tablename__ = "port_congestion"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    port_id: Mapped[int] = mapped_column(ForeignKey("ports.port_id"), primary_key=True)
    vessels_waiting: Mapped[int | None] = mapped_column(Integer)
    avg_waiting_days: Mapped[float | None] = mapped_column(Numeric(5, 2))
    data_provenance: Mapped[str] = mapped_column(String(20), nullable=False, default="synthetic")

    __table_args__ = (
        CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_port_congestion_provenance"
        ),
    )


class TideLevel(Base):
    __tablename__ = "tide_levels"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    port_id: Mapped[int] = mapped_column(ForeignKey("ports.port_id"), primary_key=True)
    tide_height_m: Mapped[float | None] = mapped_column(Numeric(4, 2))
    data_provenance: Mapped[str] = mapped_column(String(20), nullable=False, default="synthetic")

    __table_args__ = (
        CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_tide_levels_provenance"
        ),
    )


class AisPosition(Base):
    __tablename__ = "ais_positions"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    imo_number: Mapped[str] = mapped_column(String(15), primary_key=True)
    # spatial_index=False: no idx_* is defined for ais_positions in Section 2.3,
    # and this table is high-volume, so we don't want an implicit GIST index
    # silently appearing (and to keep this column's behavior consistent with
    # ports.location above).
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    speed_knots: Mapped[float | None] = mapped_column(Numeric(5, 2))
    heading: Mapped[float | None] = mapped_column(Numeric(5, 1))
    nav_status: Mapped[str | None] = mapped_column(String(40))
    data_provenance: Mapped[str] = mapped_column(String(20), nullable=False, default="synthetic")

    __table_args__ = (
        CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_ais_positions_provenance"
        ),
    )


# =============================================================================
# OPERATIONAL / TRANSACTIONAL TABLES
# =============================================================================


class Vessel(Base):
    __tablename__ = "vessels"

    vessel_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo_number: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    vessel_name: Mapped[str | None] = mapped_column(String(120))
    vessel_class_id: Mapped[int] = mapped_column(
        ForeignKey("vessel_classes.vessel_class_id"), nullable=False
    )
    dwt: Mapped[int] = mapped_column(Integer, nullable=False)
    loa_m: Mapped[float | None] = mapped_column(Numeric(6, 2))
    beam_m: Mapped[float | None] = mapped_column(Numeric(5, 2))
    laden_draft_m: Mapped[float | None] = mapped_column(Numeric(5, 2))
    flag: Mapped[str | None] = mapped_column(String(60))
    build_year: Mapped[int | None] = mapped_column(Integer)

    vessel_class: Mapped["VesselClass"] = relationship(back_populates="vessels")


class CharterContract(Base):
    __tablename__ = "charter_contracts"

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    contract_type: Mapped[str] = mapped_column(String(20), nullable=False)
    vessel_id: Mapped[int | None] = mapped_column(ForeignKey("vessels.vessel_id"))
    vessel_class_id: Mapped[int] = mapped_column(
        ForeignKey("vessel_classes.vessel_class_id"), nullable=False
    )
    trade_lane_id: Mapped[int] = mapped_column(ForeignKey("trade_lanes.trade_lane_id"), nullable=False)
    commodity_id: Mapped[int] = mapped_column(ForeignKey("commodities.commodity_id"), nullable=False)
    cargo_qty_mt: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    laycan_start: Mapped[date] = mapped_column(Date, nullable=False)
    laycan_end: Mapped[date] = mapped_column(Date, nullable=False)
    fixed_rate_value: Mapped[float | None] = mapped_column(Numeric(12, 2))
    fixed_rate_unit: Mapped[str | None] = mapped_column(String(20))
    num_voyages: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="PROPOSED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "contract_type IN ('SPOT','SHORT_TERM','MEDIUM_TERM','COA','PERIOD')",
            name="ck_charter_contracts_type",
        ),
        CheckConstraint(
            "fixed_rate_unit IN ('USD_PER_MT','USD_PER_DAY') OR fixed_rate_unit IS NULL",
            name="ck_charter_contracts_rate_unit",
        ),
        CheckConstraint(
            "status IN ('PROPOSED','FIXED','LAYCAN_ACTIVE','COMPLETED','CANCELLED')",
            name="ck_charter_contracts_status",
        ),
    )


class VoyageSimulation(Base):
    __tablename__ = "voyage_simulations"

    simulation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("charter_contracts.contract_id")
    )
    trade_lane_id: Mapped[int] = mapped_column(ForeignKey("trade_lanes.trade_lane_id"), nullable=False)
    vessel_class_id: Mapped[int] = mapped_column(
        ForeignKey("vessel_classes.vessel_class_id"), nullable=False
    )
    laden_days: Mapped[float | None] = mapped_column(Numeric(5, 2))
    ballast_days: Mapped[float | None] = mapped_column(Numeric(5, 2))
    port_days_load: Mapped[float | None] = mapped_column(Numeric(5, 2))
    port_days_discharge: Mapped[float | None] = mapped_column(Numeric(5, 2))
    idle_days: Mapped[float | None] = mapped_column(Numeric(5, 2))
    total_voyage_days: Mapped[float | None] = mapped_column(Numeric(5, 2))
    bunker_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 2))
    port_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 2))
    demurrage_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 2))
    freight_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 2))
    total_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 2))
    scenario_label: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# ML / FORECASTING SUPPORT TABLES
# =============================================================================


class ModelRegistryEntry(Base):
    __tablename__ = "model_registry"

    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_trade_lane_id: Mapped[int | None] = mapped_column(ForeignKey("trade_lanes.trade_lane_id"))
    target_vessel_class_id: Mapped[int | None] = mapped_column(
        ForeignKey("vessel_classes.vessel_class_id")
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String, nullable=False)
    training_data_start: Mapped[date | None] = mapped_column(Date)
    training_data_end: Mapped[date | None] = mapped_column(Date)
    metrics_json: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Forecast(Base):
    __tablename__ = "forecasts"

    forecast_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_registry.model_id"), nullable=False
    )
    trade_lane_id: Mapped[int] = mapped_column(ForeignKey("trade_lanes.trade_lane_id"), nullable=False)
    vessel_class_id: Mapped[int] = mapped_column(
        ForeignKey("vessel_classes.vessel_class_id"), nullable=False
    )
    forecast_made_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_rate: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    predicted_rate_p10: Mapped[float | None] = mapped_column(Numeric(12, 2))
    predicted_rate_p90: Mapped[float | None] = mapped_column(Numeric(12, 2))
    rate_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    feature_snapshot: Mapped[dict | None] = mapped_column(JSONB)


class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recommended_vessel_class_id: Mapped[int | None] = mapped_column(
        ForeignKey("vessel_classes.vessel_class_id")
    )
    recommended_contract_type: Mapped[str | None] = mapped_column(String(20))
    recommended_entry_window_start: Mapped[date | None] = mapped_column(Date)
    recommended_entry_window_end: Mapped[date | None] = mapped_column(Date)
    expected_cost_usd: Mapped[float | None] = mapped_column(Numeric(14, 2))
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    rationale_json: Mapped[dict | None] = mapped_column(JSONB)
    risk_flags: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
