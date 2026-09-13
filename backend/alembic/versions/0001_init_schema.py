"""init schema

Derived from app/db/models.py, which mirrors Section 2.3 of the implementation
plan's DDL exactly. Hypertable conversion (`create_hypertable(...)`) is issued
as raw SQL after each time-series table is created, since that's a TimescaleDB-
specific operation with no first-class Alembic/SQLAlchemy op.

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00

"""

from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # Extensions
    # ---------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ---------------------------------------------------------------
    # Reference / master data
    # ---------------------------------------------------------------
    op.create_table(
        "vessel_classes",
        sa.Column("vessel_class_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("class_name", sa.String(50), nullable=False, unique=True),
        sa.Column("dwt_min", sa.Integer(), nullable=False),
        sa.Column("dwt_max", sa.Integer(), nullable=False),
        sa.Column("typical_loa_m", sa.Numeric(6, 2)),
        sa.Column("typical_beam_m", sa.Numeric(5, 2)),
        sa.Column("typical_laden_draft_m", sa.Numeric(5, 2)),
    )

    op.create_table(
        "ports",
        sa.Column("port_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("port_code", sa.String(10), nullable=False, unique=True),
        sa.Column("port_name", sa.String(120), nullable=False),
        sa.Column("country", sa.String(80), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("max_loa_m", sa.Numeric(6, 2)),
        sa.Column("max_beam_m", sa.Numeric(5, 2)),
        sa.Column("max_draft_charted_m", sa.Numeric(5, 2)),
        sa.Column("tidal_range_m", sa.Numeric(4, 2)),
        sa.Column("cargo_handling_rate_mt_per_day", sa.Numeric(10, 2)),
        sa.Column("berth_count", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('LOAD','DISCHARGE','BOTH')", name="ck_ports_role"),
    )

    op.create_table(
        "commodities",
        sa.Column("commodity_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("commodity_name", sa.String(60), nullable=False, unique=True),
        sa.Column("typical_stowage_factor", sa.Numeric(6, 3)),
    )

    op.create_table(
        "trade_lanes",
        sa.Column("trade_lane_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "origin_port_id", sa.Integer(), sa.ForeignKey("ports.port_id"), nullable=False
        ),
        sa.Column(
            "destination_port_id", sa.Integer(), sa.ForeignKey("ports.port_id"), nullable=False
        ),
        sa.Column("sea_distance_nm", sa.Numeric(8, 1)),
        sa.Column("typical_transit_days_laden", sa.Numeric(5, 1)),
        sa.Column("commodity", sa.String(60), nullable=False, server_default="coal"),
        sa.UniqueConstraint(
            "origin_port_id", "destination_port_id", "commodity", name="uq_trade_lanes_route_commodity"
        ),
    )

    # ---------------------------------------------------------------
    # Time-series (TimescaleDB hypertables)
    # ---------------------------------------------------------------
    op.create_table(
        "freight_rates",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column(
            "trade_lane_id",
            sa.Integer(),
            sa.ForeignKey("trade_lanes.trade_lane_id"),
            primary_key=True,
        ),
        sa.Column(
            "vessel_class_id",
            sa.Integer(),
            sa.ForeignKey("vessel_classes.vessel_class_id"),
            primary_key=True,
        ),
        sa.Column("rate_type", sa.String(20), primary_key=True),
        sa.Column("rate_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("rate_unit", sa.String(20), nullable=False),
        sa.Column("data_provenance", sa.String(20), nullable=False, server_default="synthetic"),
        sa.Column("source", sa.String(80)),
        sa.CheckConstraint("rate_type IN ('SPOT','TCE','COA','PERIOD')", name="ck_freight_rates_type"),
        sa.CheckConstraint(
            "rate_unit IN ('USD_PER_MT','USD_PER_DAY')", name="ck_freight_rates_unit"
        ),
        sa.CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_freight_rates_provenance"
        ),
    )
    op.execute("SELECT create_hypertable('freight_rates', 'time')")

    # NOTE: deviates from the plan's literal DDL here — see the matching
    # comment on app/db/models.py::BunkerPrice for why the nullable port_id
    # can't actually be part of the primary key.
    op.create_table(
        "bunker_prices",
        sa.Column("bunker_price_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("port_id", sa.Integer(), sa.ForeignKey("ports.port_id")),
        sa.Column("fuel_grade", sa.String(20), nullable=False),
        sa.Column("price_usd_per_mt", sa.Numeric(10, 2), nullable=False),
        sa.Column("data_provenance", sa.String(20), nullable=False, server_default="synthetic"),
        sa.CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_bunker_prices_provenance"
        ),
    )
    op.execute("SELECT create_hypertable('bunker_prices', 'time')")
    op.execute(
        "CREATE UNIQUE INDEX ux_bunker_prices_port ON bunker_prices (time, fuel_grade, port_id) "
        "WHERE port_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_bunker_prices_global ON bunker_prices (time, fuel_grade) "
        "WHERE port_id IS NULL"
    )

    op.create_table(
        "commodity_prices",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column(
            "commodity_id",
            sa.Integer(),
            sa.ForeignKey("commodities.commodity_id"),
            primary_key=True,
        ),
        sa.Column("price_usd_per_mt", sa.Numeric(10, 2), nullable=False),
        sa.Column("data_provenance", sa.String(20), nullable=False, server_default="synthetic"),
        sa.CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_commodity_prices_provenance"
        ),
    )
    op.execute("SELECT create_hypertable('commodity_prices', 'time')")

    op.create_table(
        "port_congestion",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("port_id", sa.Integer(), sa.ForeignKey("ports.port_id"), primary_key=True),
        sa.Column("vessels_waiting", sa.Integer()),
        sa.Column("avg_waiting_days", sa.Numeric(5, 2)),
        sa.Column("data_provenance", sa.String(20), nullable=False, server_default="synthetic"),
        sa.CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_port_congestion_provenance"
        ),
    )
    op.execute("SELECT create_hypertable('port_congestion', 'time')")

    op.create_table(
        "tide_levels",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("port_id", sa.Integer(), sa.ForeignKey("ports.port_id"), primary_key=True),
        sa.Column("tide_height_m", sa.Numeric(4, 2)),
        sa.Column("data_provenance", sa.String(20), nullable=False, server_default="synthetic"),
        sa.CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_tide_levels_provenance"
        ),
    )
    op.execute("SELECT create_hypertable('tide_levels', 'time')")

    op.create_table(
        "ais_positions",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("imo_number", sa.String(15), primary_key=True),
        sa.Column(
            "location",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("speed_knots", sa.Numeric(5, 2)),
        sa.Column("heading", sa.Numeric(5, 1)),
        sa.Column("nav_status", sa.String(40)),
        sa.Column("data_provenance", sa.String(20), nullable=False, server_default="synthetic"),
        sa.CheckConstraint(
            "data_provenance IN ('live','proxy','synthetic')", name="ck_ais_positions_provenance"
        ),
    )
    op.execute("SELECT create_hypertable('ais_positions', 'time')")

    # ---------------------------------------------------------------
    # Operational / transactional tables
    # ---------------------------------------------------------------
    op.create_table(
        "vessels",
        sa.Column("vessel_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("imo_number", sa.String(15), nullable=False, unique=True),
        sa.Column("vessel_name", sa.String(120)),
        sa.Column(
            "vessel_class_id",
            sa.Integer(),
            sa.ForeignKey("vessel_classes.vessel_class_id"),
            nullable=False,
        ),
        sa.Column("dwt", sa.Integer(), nullable=False),
        sa.Column("loa_m", sa.Numeric(6, 2)),
        sa.Column("beam_m", sa.Numeric(5, 2)),
        sa.Column("laden_draft_m", sa.Numeric(5, 2)),
        sa.Column("flag", sa.String(60)),
        sa.Column("build_year", sa.Integer()),
    )

    op.create_table(
        "charter_contracts",
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("contract_type", sa.String(20), nullable=False),
        sa.Column("vessel_id", sa.Integer(), sa.ForeignKey("vessels.vessel_id")),
        sa.Column(
            "vessel_class_id",
            sa.Integer(),
            sa.ForeignKey("vessel_classes.vessel_class_id"),
            nullable=False,
        ),
        sa.Column(
            "trade_lane_id", sa.Integer(), sa.ForeignKey("trade_lanes.trade_lane_id"), nullable=False
        ),
        sa.Column(
            "commodity_id", sa.Integer(), sa.ForeignKey("commodities.commodity_id"), nullable=False
        ),
        sa.Column("cargo_qty_mt", sa.Numeric(12, 2), nullable=False),
        sa.Column("laycan_start", sa.Date(), nullable=False),
        sa.Column("laycan_end", sa.Date(), nullable=False),
        sa.Column("fixed_rate_value", sa.Numeric(12, 2)),
        sa.Column("fixed_rate_unit", sa.String(20)),
        sa.Column("num_voyages", sa.Integer(), server_default="1"),
        sa.Column("status", sa.String(20), server_default="PROPOSED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "contract_type IN ('SPOT','SHORT_TERM','MEDIUM_TERM','COA','PERIOD')",
            name="ck_charter_contracts_type",
        ),
        sa.CheckConstraint(
            "fixed_rate_unit IN ('USD_PER_MT','USD_PER_DAY') OR fixed_rate_unit IS NULL",
            name="ck_charter_contracts_rate_unit",
        ),
        sa.CheckConstraint(
            "status IN ('PROPOSED','FIXED','LAYCAN_ACTIVE','COMPLETED','CANCELLED')",
            name="ck_charter_contracts_status",
        ),
    )

    op.create_table(
        "voyage_simulations",
        sa.Column(
            "simulation_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("charter_contracts.contract_id")
        ),
        sa.Column(
            "trade_lane_id", sa.Integer(), sa.ForeignKey("trade_lanes.trade_lane_id"), nullable=False
        ),
        sa.Column(
            "vessel_class_id",
            sa.Integer(),
            sa.ForeignKey("vessel_classes.vessel_class_id"),
            nullable=False,
        ),
        sa.Column("laden_days", sa.Numeric(5, 2)),
        sa.Column("ballast_days", sa.Numeric(5, 2)),
        sa.Column("port_days_load", sa.Numeric(5, 2)),
        sa.Column("port_days_discharge", sa.Numeric(5, 2)),
        sa.Column("idle_days", sa.Numeric(5, 2)),
        sa.Column("total_voyage_days", sa.Numeric(5, 2)),
        sa.Column("bunker_cost_usd", sa.Numeric(12, 2)),
        sa.Column("port_cost_usd", sa.Numeric(12, 2)),
        sa.Column("demurrage_cost_usd", sa.Numeric(12, 2)),
        sa.Column("freight_cost_usd", sa.Numeric(12, 2)),
        sa.Column("total_cost_usd", sa.Numeric(12, 2)),
        sa.Column("scenario_label", sa.String(40)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ---------------------------------------------------------------
    # ML / forecasting support tables
    # ---------------------------------------------------------------
    op.create_table(
        "model_registry",
        sa.Column(
            "model_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("model_name", sa.String(80), nullable=False),
        sa.Column("model_type", sa.String(40), nullable=False),
        sa.Column("target_trade_lane_id", sa.Integer(), sa.ForeignKey("trade_lanes.trade_lane_id")),
        sa.Column(
            "target_vessel_class_id", sa.Integer(), sa.ForeignKey("vessel_classes.vessel_class_id")
        ),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("training_data_start", sa.Date()),
        sa.Column("training_data_end", sa.Date()),
        sa.Column("metrics_json", postgresql.JSONB()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "forecasts",
        sa.Column(
            "forecast_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_registry.model_id"),
            nullable=False,
        ),
        sa.Column(
            "trade_lane_id", sa.Integer(), sa.ForeignKey("trade_lanes.trade_lane_id"), nullable=False
        ),
        sa.Column(
            "vessel_class_id",
            sa.Integer(),
            sa.ForeignKey("vessel_classes.vessel_class_id"),
            nullable=False,
        ),
        sa.Column(
            "forecast_made_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("predicted_rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("predicted_rate_p10", sa.Numeric(12, 2)),
        sa.Column("predicted_rate_p90", sa.Numeric(12, 2)),
        sa.Column("rate_unit", sa.String(20), nullable=False),
        sa.Column("feature_snapshot", postgresql.JSONB()),
    )

    op.create_table(
        "recommendations",
        sa.Column(
            "recommendation_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("request_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "recommended_vessel_class_id", sa.Integer(), sa.ForeignKey("vessel_classes.vessel_class_id")
        ),
        sa.Column("recommended_contract_type", sa.String(20)),
        sa.Column("recommended_entry_window_start", sa.Date()),
        sa.Column("recommended_entry_window_end", sa.Date()),
        sa.Column("expected_cost_usd", sa.Numeric(14, 2)),
        sa.Column("confidence_score", sa.Numeric(4, 3)),
        sa.Column("rationale_json", postgresql.JSONB()),
        sa.Column("risk_flags", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ---------------------------------------------------------------
    # Indexes for common query patterns (Section 2.3)
    # ---------------------------------------------------------------
    op.create_index(
        "idx_freight_rates_lane_class",
        "freight_rates",
        ["trade_lane_id", "vessel_class_id", sa.text("time DESC")],
    )
    op.create_index(
        "idx_forecasts_lane_class", "forecasts", ["trade_lane_id", "vessel_class_id", "target_date"]
    )
    op.execute("CREATE INDEX idx_ports_location ON ports USING GIST (location)")


def downgrade() -> None:
    op.drop_index("idx_ports_location", table_name="ports")
    op.drop_index("idx_forecasts_lane_class", table_name="forecasts")
    op.drop_index("idx_freight_rates_lane_class", table_name="freight_rates")
    op.execute("DROP INDEX IF EXISTS ux_bunker_prices_global")
    op.execute("DROP INDEX IF EXISTS ux_bunker_prices_port")

    op.drop_table("recommendations")
    op.drop_table("forecasts")
    op.drop_table("model_registry")
    op.drop_table("voyage_simulations")
    op.drop_table("charter_contracts")
    op.drop_table("vessels")
    op.drop_table("ais_positions")
    op.drop_table("tide_levels")
    op.drop_table("port_congestion")
    op.drop_table("commodity_prices")
    op.drop_table("bunker_prices")
    op.drop_table("freight_rates")
    op.drop_table("trade_lanes")
    op.drop_table("commodities")
    op.drop_table("ports")
    op.drop_table("vessel_classes")
