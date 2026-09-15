from datetime import date, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.session import init_db
from app.optimization.recommendation_service import RecommendationService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    init_db(session)
    yield session
    session.close()


def test_recommendation_service_for_coal_cargo(db_session):
    svc = RecommendationService(db_session)
    laycan_start = date.today() + timedelta(days=20)
    laycan_end = laycan_start + timedelta(days=10)

    rec = svc.generate_recommendation(
        commodity="coking_coal",
        cargo_qty_mt=75000.0,
        destination_port_code="INPRT",
        laycan_start=laycan_start,
        laycan_end=laycan_end
    )

    assert rec["commodity"] == "coking_coal"
    assert rec["cargo_qty_mt"] == 75000.0
    assert rec["recommended_vessel_class"] in ["Panamax", "Capesize", "Supramax"]
    assert isinstance(rec["recommended_origin_port"], str) and len(rec["recommended_origin_port"]) > 0
    assert rec["expected_total_cost_usd"] > 0
    assert rec["cost_per_mt_usd"] > 0
    assert len(rec["charter_scenarios"]) == 3
    assert "rationale" in rec


