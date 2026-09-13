from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional
import pandas as pd

from app.schemas.forecast import ForecastResult


class BaseForecaster(ABC):
    """
    Abstract Base Class for all freight forecasting models in FreightIQ.
    Ensures interchangeable Tier-0 models (LightGBM, Prophet, SARIMAX) and Tier-1 models (TFT, Chronos).
    """

    def __init__(self, model_name: str, target_variable: str = "TCE_rate", rate_unit: str = "USD_PER_DAY"):
        self.model_name = model_name
        self.target_variable = target_variable
        self.rate_unit = rate_unit
        self.version = "1.0.0"
        self.is_fitted = False
        self.feature_columns: List[str] = []

    @abstractmethod
    def fit(self, panel_df: pd.DataFrame, trade_lane_id: Optional[int] = None, vessel_class_id: Optional[int] = None) -> None:
        """
        Fits the model on the provided feature panel DataFrame.
        """
        pass

    @abstractmethod
    def predict(
        self,
        panel_df: pd.DataFrame,
        trade_lane_id: int,
        vessel_class_id: int,
        target_date: date,
        horizon_days: int
    ) -> ForecastResult:
        """
        Generates a forecast for a specific (lane, class, target_date, horizon).
        Returns point forecast, p10/p90 prediction intervals, and feature audit snapshot.
        """
        pass

    @abstractmethod
    def save(self, filepath: str) -> None:
        """
        Serializes model state/artifacts to disk.
        """
        pass

    @classmethod
    @abstractmethod
    def load(cls, filepath: str) -> "BaseForecaster":
        """
        Deserializes model state from disk.
        """
        pass


