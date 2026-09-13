import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class VesselClass(Base):
    __tablename__ = "vessel_classes"

    vessel_class_id = Column(Integer, primary_key=True, autoincrement=True)
    class_name = Column(String(50), unique=True, nullable=False)
    dwt_min = Column(Integer, nullable=False)
    dwt_max = Column(Integer, nullable=False)
    typical_loa_m = Column(Numeric(6, 2), nullable=True)
    typical_beam_m = Column(Numeric(5, 2), nullable=True)
    typical_laden_draft_m = Column(Numeric(5, 2), nullable=True)
    bunker_consumption_tpd = Column(Float, nullable=False, default=25.0)
    typical_port_dues_usd = Column(Float, nullable=False, default=40000.0)

    trade_lanes = relationship("TradeLane", back_populates="vessel_class")


class Port(Base):
    __tablename__ = "ports"

    port_id = Column(Integer, primary_key=True, autoincrement=True)
    port_code = Column(String(10), unique=True, nullable=False)
    port_name = Column(String(120), nullable=False)
    country = Column(String(80), nullable=False)
    role = Column(String(20), nullable=False)  # LOAD, DISCHARGE, BOTH
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    max_loa_m = Column(Numeric(6, 2), nullable=True)
    max_beam_m = Column(Numeric(5, 2), nullable=True)
    max_draft_charted_m = Column(Numeric(5, 2), nullable=True)
    tidal_range_m = Column(Numeric(4, 2), nullable=True)
    cargo_handling_rate_mt_per_day = Column(Numeric(10, 2), nullable=True)
    berth_count = Column(Integer, nullable=True, default=0)
    notes = Column(Text, nullable=True)
    source = Column(String(255), nullable=True)
    figures_verified = Column(Boolean, nullable=True, default=False)


class Commodity(Base):
    __tablename__ = "commodities"

    commodity_id = Column(Integer, primary_key=True, autoincrement=True)
    commodity_name = Column(String(60), unique=True, nullable=False)
    typical_stowage_factor = Column(Float, nullable=False, default=1.3)


class TradeLane(Base):
    __tablename__ = "trade_lanes"

    trade_lane_id = Column(Integer, primary_key=True, autoincrement=True)
    origin_port_code = Column(String(10), nullable=False)
    destination_port_code = Column(String(10), nullable=False)
    vessel_class_id = Column(Integer, ForeignKey("vessel_classes.vessel_class_id"), nullable=True)
    sea_distance_nm = Column(Numeric(8, 1), nullable=False)
    typical_transit_days_laden = Column(Numeric(5, 1), nullable=True)
    commodity = Column(String(60), nullable=False, default="coal")

    vessel_class = relationship("VesselClass", back_populates="trade_lanes")


class FreightRate(Base):
    __tablename__ = "freight_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, nullable=False)
    trade_lane_id = Column(Integer, ForeignKey("trade_lanes.trade_lane_id"), nullable=False)
    vessel_class_id = Column(Integer, ForeignKey("vessel_classes.vessel_class_id"), nullable=False)
    rate_type = Column(String(20), nullable=False)  # SPOT, TCE, COA, PERIOD
    rate_value = Column(Float, nullable=False)
    rate_unit = Column(String(20), nullable=False)  # USD_PER_MT, USD_PER_DAY
    data_provenance = Column(String(20), nullable=False, default="synthetic")


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    model_id = Column(String(36), primary_key=True, default=generate_uuid)
    model_name = Column(String(80), nullable=False)
    model_type = Column(String(40), nullable=False)  # lightgbm_quantile, prophet, sarimax, tft, chronos
    target_trade_lane_id = Column(Integer, ForeignKey("trade_lanes.trade_lane_id"), nullable=True)
    target_vessel_class_id = Column(Integer, ForeignKey("vessel_classes.vessel_class_id"), nullable=True)
    target_horizon_days = Column(Integer, nullable=True)
    target_variable = Column(String(40), nullable=False, default="TCE_rate")
    version = Column(String(20), nullable=False)
    artifact_path = Column(Text, nullable=False)
    training_data_start = Column(Date, nullable=True)
    training_data_end = Column(Date, nullable=True)
    metrics_json = Column(JSON, nullable=True)  # {"rmse": ..., "mape": ..., "directional_accuracy": ..., "pinball_loss": ...}
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Forecast(Base):
    __tablename__ = "forecasts"

    forecast_id = Column(String(36), primary_key=True, default=generate_uuid)
    model_id = Column(String(36), ForeignKey("model_registry.model_id"), nullable=False)
    trade_lane_id = Column(Integer, ForeignKey("trade_lanes.trade_lane_id"), nullable=False)
    vessel_class_id = Column(Integer, ForeignKey("vessel_classes.vessel_class_id"), nullable=False)
    forecast_made_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    target_date = Column(Date, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    predicted_rate = Column(Float, nullable=False)
    predicted_rate_p10 = Column(Float, nullable=True)
    predicted_rate_p90 = Column(Float, nullable=True)
    rate_unit = Column(String(20), nullable=False)
    feature_snapshot = Column(JSON, nullable=True)


class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id = Column(String(36), primary_key=True, default=generate_uuid)
    request_payload = Column(JSON, nullable=False)
    recommended_vessel_class_id = Column(Integer, ForeignKey("vessel_classes.vessel_class_id"), nullable=True)
    recommended_contract_type = Column(String(20), nullable=True)
    recommended_entry_window_start = Column(Date, nullable=True)
    recommended_entry_window_end = Column(Date, nullable=True)
    expected_cost_usd = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    candidates_considered_count = Column(Integer, nullable=True, default=0)
    feasible_candidates_count = Column(Integer, nullable=True, default=0)
    rejected_candidates_json = Column(JSON, nullable=True)
    rationale_json = Column(JSON, nullable=True)
    risk_flags = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
