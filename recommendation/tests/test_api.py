import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.session import get_db, init_db
from app.main import app

engine = create_engine("sqlite:///./test_api.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
db_init = TestingSessionLocal()
init_db(db_init)
db_init.close()


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_forecast_endpoint():
    response = client.get("/api/forecasts?trade_lane_id=1&vessel_class_id=3&horizons=7&horizons=30")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["trade_lane_id"] == 1
    assert data[0]["vessel_class_id"] == 3
    assert data[0]["point_forecast"] > 0


def test_recommendation_endpoint():
    payload = {
        "commodity": "coking_coal",
        "cargo_qty_mt": 75000,
        "destination_port_code": "INPRT",
        "laycan_start": "2026-10-01",
        "laycan_end": "2026-10-15"
    }
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == "coking_coal"
    assert data["cargo_qty_mt"] == 75000
    assert data["recommended_vessel_class"] in ["Panamax", "Capesize", "Supramax"]
    assert "candidates_considered_count" in data
    assert data["candidates_considered_count"] > 0


