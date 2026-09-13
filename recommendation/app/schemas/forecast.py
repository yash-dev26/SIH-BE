from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ForecastResult(BaseModel):
    point_forecast: float = Field(..., description="Predicted freight rate point estimate")
    p10: Optional[float] = Field(None, description="10th percentile lower prediction interval")
    p90: Optional[float] = Field(None, description="90th percentile upper prediction interval")
    rate_unit: str = Field("USD_PER_DAY", description="Unit of the rate (e.g. USD_PER_DAY or USD_PER_MT)")
    target_date: date = Field(..., description="Date for which prediction applies")
    horizon_days: int = Field(..., description="Forecast horizon in days (e.g. 7, 30, 90, 180)")
    trade_lane_id: int = Field(..., description="Target trade lane ID")
    vessel_class_id: int = Field(..., description="Target vessel class ID")
    model_version: str = Field(..., description="Version string of the generating model")
    model_id: Optional[str] = Field(None, description="UUID of active model used")
    model_fallback_used: bool = Field(False, description="Whether fallback model was used")
    model_fallback_reason: Optional[str] = Field(None, description="Reason for fallback or model selection details")
    model_training_rows: Optional[int] = Field(None, description="Number of training rows used to train active model")
    feature_snapshot: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Input features used for inference audit trail")


class ForecastRequest(BaseModel):
    trade_lane_id: int = Field(..., description="Trade lane ID")
    vessel_class_id: int = Field(..., description="Vessel class ID")
    horizons: List[int] = Field(default=[7, 30, 90, 180], description="List of forecast horizons in days")
    as_of_date: Optional[date] = Field(default=None, description="As-of date for inference (defaults to today)")


class ModelTrainRequest(BaseModel):
    trade_lane_ids: Optional[List[int]] = Field(default=None, description="List of trade lane IDs to train models for (None = all)")
    vessel_class_ids: Optional[List[int]] = Field(default=None, description="List of vessel class IDs to train models for (None = all)")
    horizons: List[int] = Field(default=[7, 30, 90, 180], description="Target horizons")
    target_variable: str = Field(default="TCE_rate", description="Target variable (TCE_rate or spot_rate)")


class ModelMetricsSchema(BaseModel):
    rmse: float
    mape: float
    directional_accuracy: float
    pinball_loss: Optional[float] = None


class ModelRegistryResponse(BaseModel):
    model_id: str
    model_name: str
    model_type: str
    target_trade_lane_id: Optional[int]
    target_vessel_class_id: Optional[int]
    target_horizon_days: Optional[int]
    target_variable: str
    version: str
    metrics_json: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
