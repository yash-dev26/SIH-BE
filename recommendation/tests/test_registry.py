import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.forecasting.models.lightgbm_quantile import LightGBMQuantileForecaster
from app.forecasting.registry import ModelRegistryManager
from app.features.mock_panel_generator import generate_synthetic_training_panel


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_registry_registration_and_promotion(db_session):
    panel = generate_synthetic_training_panel(num_days=400)
    forecaster = LightGBMQuantileForecaster()
    forecaster.fit(panel, trade_lane_id=1, vessel_class_id=3)

    mgr = ModelRegistryManager(db_session)

    # 1. Register first model with MAPE 15.0%
    model1 = mgr.register_model(
        forecaster=forecaster,
        trade_lane_id=1,
        vessel_class_id=3,
        metrics={"rmse": 1200.0, "mape": 15.0, "directional_accuracy": 65.0}
    )

    # First model auto-promotes because no champion existed
    promoted1 = mgr.promote_if_better(model1.model_id, min_improvement_pct=2.0)
    assert promoted1 is True
    assert model1.is_active is True

    # 2. Register candidate model with MAPE 14.5% (only 0.5% improvement -> should be REJECTED by 2% gate)
    model2 = mgr.register_model(
        forecaster=forecaster,
        trade_lane_id=1,
        vessel_class_id=3,
        metrics={"rmse": 1150.0, "mape": 14.5, "directional_accuracy": 66.0}
    )
    promoted2 = mgr.promote_if_better(model2.model_id, min_improvement_pct=2.0)
    assert promoted2 is False
    assert model2.is_active is False

    # 3. Register candidate model with MAPE 12.0% (3.0% improvement -> should be PROMOTED)
    model3 = mgr.register_model(
        forecaster=forecaster,
        trade_lane_id=1,
        vessel_class_id=3,
        metrics={"rmse": 950.0, "mape": 12.0, "directional_accuracy": 72.0}
    )
    promoted3 = mgr.promote_if_better(model3.model_id, min_improvement_pct=2.0)
    assert promoted3 is True
    assert model3.is_active is True
    db_session.refresh(model1)
    assert model1.is_active is False  # Previous champion demoted


