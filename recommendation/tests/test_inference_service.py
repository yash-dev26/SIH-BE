from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.forecasting.inference_service import ForecastingService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_inference_naive_fallback_when_no_active_model(db_session):
    service = ForecastingService(db_session)
    results = service.get_forecast(trade_lane_id=1, vessel_class_id=3, horizons=[7, 30])

    assert len(results) == 2
    for res in results:
        assert res.point_forecast > 0
        assert res.model_version == "0.0.0_naive_fallback"
        assert res.model_id == "NAIVE_FALLBACK"
        assert res.trade_lane_id == 1
        assert res.vessel_class_id == 3
