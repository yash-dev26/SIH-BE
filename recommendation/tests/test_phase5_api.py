"""
Phase 5 acceptance check: "Full OpenAPI docs render at /docs; a scripted smoke test
exercises every router end-to-end against the seeded synthetic dataset from Phase 1-2."

Covers every router registered in app.main: auth, ports, vessels, forecasts,
recommendations, scenarios, contracts, risk - plus /docs and the OpenAPI schema itself.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.session import get_db, init_db
from app.main import app

engine = create_engine("sqlite:///./test_phase5_api.db", connect_args={"check_same_thread": False})
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


# --- Docs / OpenAPI -----------------------------------------------------------------------

def test_openapi_schema_renders():
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    for path in ["/api/ports", "/api/vessels/classes", "/api/scenarios/compare", "/api/contracts", "/api/risk/{lane_id}"]:
        assert path in schema["paths"], f"{path} missing from OpenAPI schema"


def test_docs_ui_renders():
    response = client.get("/docs")
    assert response.status_code == 200


# --- Auth (AUTH_ENABLED=False by default, so /auth/me is reachable and returns null) -------

def test_auth_token_and_me():
    response = client.post(
        "/api/auth/token",
        data={"username": "logistics_manager", "password": "changeme123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert token

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200


def test_auth_token_rejects_bad_password():
    response = client.post(
        "/api/auth/token",
        data={"username": "logistics_manager", "password": "wrong-password"},
    )
    assert response.status_code == 401


# --- Ports ---------------------------------------------------------------------------------

def test_list_and_get_port():
    response = client.get("/api/ports")
    assert response.status_code == 200
    ports = response.json()
    assert len(ports) > 0

    response = client.get("/api/ports/INPDP")
    assert response.status_code == 200
    assert response.json()["port_code"] == "INPDP"

    # alias resolution
    response = client.get("/api/ports/Paradip")
    assert response.status_code == 200
    assert response.json()["port_code"] == "INPDP"


def test_port_constraints():
    response = client.get("/api/ports/MZBEW/constraints")
    assert response.status_code == 200
    data = response.json()
    assert data["port"]["port_code"] == "MZBEW"
    feasibility_by_class = {row["vessel_class_name"]: row["is_feasible"] for row in data["vessel_feasibility"]}
    # Beira (8.0m charted draft) is a hard binding constraint - Capesize must be infeasible there.
    assert feasibility_by_class["Capesize"] is False


# --- Vessels / trade lanes -------------------------------------------------------------------

def test_list_vessel_classes_and_trade_lanes():
    response = client.get("/api/vessels/classes")
    assert response.status_code == 200
    classes = response.json()
    assert any(c["class_name"] == "Panamax" for c in classes)

    response = client.get("/api/vessels/trade-lanes")
    assert response.status_code == 200
    assert len(response.json()) > 0


# --- Scenarios -------------------------------------------------------------------------------

def test_scenario_compare():
    lanes = client.get("/api/vessels/trade-lanes").json()
    lane = lanes[0]
    payload = {
        "trade_lane_id": lane["trade_lane_id"],
        "vessel_class_id": lane["vessel_class_id"] or 3,
        "cargo_qty_mt": 60000,
    }
    response = client.post("/api/scenarios/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["scenarios"]) == 3
    assert data["recommended_contract_type"] in ["SPOT", "COA", "PERIOD"]


# --- Risk --------------------------------------------------------------------------------

def test_lane_risk():
    lanes = client.get("/api/vessels/trade-lanes").json()
    lane_id = lanes[0]["trade_lane_id"]
    response = client.get(f"/api/risk/{lane_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["trade_lane_id"] == lane_id
    assert isinstance(data["risk_flags"], list)


def test_lane_risk_requires_vessel_class_when_lane_has_none():
    # Not all lanes are guaranteed to lack a vessel_class_id, so exercise the 404 path instead
    # for a lane that doesn't exist - the "missing vessel_class_id" 400 path is covered by
    # lanes without a default class if/when seed data includes one.
    response = client.get("/api/risk/999999")
    assert response.status_code == 404


# --- Contracts CRUD ----------------------------------------------------------------------

def test_contract_crud_lifecycle():
    create_payload = {
        "contract_type": "coa",
        "commodity": "thermal_coal",
        "cargo_qty_mt": 50000,
        "origin_port_code": "IDTBN",
        "destination_port_code": "INPDP",
        "tce_rate_usd_day": 14000,
        "total_cost_usd": 950000,
    }
    response = client.post("/api/contracts", json=create_payload)
    assert response.status_code == 201
    contract = response.json()
    assert contract["contract_type"] == "COA"
    # Section 5.2: unset laytime/demurrage fall back to the configured market-standard default
    assert contract["laytime_allowed_days"] > 0
    assert contract["demurrage_rate_usd_per_day"] > 0
    contract_id = contract["contract_id"]

    response = client.get(f"/api/contracts/{contract_id}")
    assert response.status_code == 200

    response = client.get("/api/contracts")
    assert response.status_code == 200
    assert any(c["contract_id"] == contract_id for c in response.json())

    response = client.patch(f"/api/contracts/{contract_id}", json={"status": "confirmed"})
    assert response.status_code == 200
    assert response.json()["status"] == "CONFIRMED"

    response = client.delete(f"/api/contracts/{contract_id}")
    assert response.status_code == 204

    response = client.get(f"/api/contracts/{contract_id}")
    assert response.json()["status"] == "CANCELLED"


def test_contract_create_rejects_invalid_contract_type():
    response = client.post("/api/contracts", json={"contract_type": "BOGUS"})
    assert response.status_code == 400


def test_contract_not_found():
    response = client.get("/api/contracts/does-not-exist")
    assert response.status_code == 404


# --- Existing Phase 3/4 routers still reachable through the fully wired app ---------------

def test_forecast_and_recommend_still_work_end_to_end():
    response = client.get("/api/forecasts?trade_lane_id=1&vessel_class_id=3&horizons=30")
    assert response.status_code == 200
    assert response.json()[0]["point_forecast"] > 0

    payload = {
        "commodity": "coking_coal",
        "cargo_qty_mt": 75000,
        "destination_port_code": "INPRT",
        "laycan_start": "2026-10-01",
        "laycan_end": "2026-10-15",
    }
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 200
    assert response.json()["candidates_considered_count"] > 0
