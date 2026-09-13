from datetime import date
from typing import List, Optional
import pandas as pd

from app.features.mock_panel_generator import generate_synthetic_training_panel


def get_training_panel(
    as_of_date: Optional[date] = None,
    lanes: Optional[List[int]] = None,
    classes: Optional[List[int]] = None,
    num_days: int = 1825
) -> pd.DataFrame:
    """
    Contract interface for Phase 3 models.
    Retrieves the complete model training feature panel DataFrame indexed by (date, trade_lane_id, vessel_class_id).
    
    When integrated with Phase 2, this function queries the feature store / Postgres tables.
    In standalone mode, it uses the synthetic generator.
    """
    return generate_synthetic_training_panel(
        as_of_date=as_of_date,
        lanes=lanes,
        classes=classes,
        num_days=num_days
    )


