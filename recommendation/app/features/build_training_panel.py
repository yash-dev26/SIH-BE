import logging
from datetime import date
from typing import List, Optional
import pandas as pd

from app.features.mock_panel_generator import generate_synthetic_training_panel
from app.features.real_dataset_loader import find_dataset_dir, load_real_training_panel

logger = logging.getLogger(__name__)


def get_training_panel(
    as_of_date: Optional[date] = None,
    lanes: Optional[List[int]] = None,
    classes: Optional[List[int]] = None,
    num_days: int = 1825
) -> pd.DataFrame:
    """
    Contract interface for Phase 3 models.
    Retrieves the complete model training feature panel DataFrame indexed by (date, trade_lane_id, vessel_class_id).

    Loads real historical dataset from dataset/ (BDI Index, Daily Bunker Fuel Prices, Monthly Commodity Prices).
    Falls back to synthetic panel generator if real dataset files are unavailable.
    """
    dataset_dir = find_dataset_dir()
    if dataset_dir:
        try:
            logger.info(f"Loading real historical dataset panel from {dataset_dir}...")
            return load_real_training_panel(dataset_dir=dataset_dir, lanes=lanes, classes=classes)
        except Exception as e:
            logger.warning(f"Failed to load real dataset panel: {e}. Falling back to synthetic generator.")

    return generate_synthetic_training_panel(
        as_of_date=as_of_date,
        lanes=lanes,
        classes=classes,
        num_days=num_days
    )


