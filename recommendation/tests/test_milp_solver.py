from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.session import init_db
from app.optimization.constraints import filter_feasible_lanes_and_vessels
from app.optimization.idle_mitigation import score_idle_mitigation_opportunities
from app.optimization.milp_solver import ENTRY_HORIZONS_DAYS, solve_multi_parcel_allocation
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


def _laycan(offset_days=20, window_days=60):
    start = date.today() + timedelta(days=offset_days)
    return start, start + timedelta(days=window_days)


def test_multi_parcel_recommendation_assigns_feasible_parcels(db_session):
    svc = RecommendationService(db_session)
    laycan_start, laycan_end = _laycan()

    parcels = [
        {
            "parcel_id": "P1",
            "commodity": "coking_coal",
            "cargo_qty_mt": 75000.0,
            "destination_port_code": "INPRT",
            "laycan_start": laycan_start,
            "laycan_end": laycan_end,
        },
        {
            "parcel_id": "P2",
            "commodity": "thermal_coal",
            "cargo_qty_mt": 55000.0,
            "destination_port_code": "INVTZ",
            "laycan_start": laycan_start,
            "laycan_end": laycan_end,
        },
    ]

    result = svc.generate_multi_parcel_recommendation(parcels=parcels, spot_cap_ratio=0.4)

    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    assert result["total_cost_usd"] > 0
    assigned_ids = {a["parcel_id"] for a in result["assignments"]}
    assert assigned_ids == {"P1", "P2"}
    for a in result["assignments"]:
        assert a["contract_type"] in ("SPOT", "SHORT_TERM", "COA", "PERIOD")
        assert a["horizon_days"] in ENTRY_HORIZONS_DAYS
        assert a["cost_breakdown"]["total_cost_usd"] > 0
        assert "binding_constraints" in a["rationale"]


def test_spot_cap_ratio_is_respected_across_the_book(db_session):
    laycan_start, laycan_end = _laycan()
    parcels = [
        {"parcel_id": f"P{i}", "cargo_qty_mt": 60000.0, "destination_port_code": "INPRT",
         "laycan_start": laycan_start, "laycan_end": laycan_end}
        for i in range(4)
    ]
    feasible_options_by_parcel = {}
    forecasts_by_option = {}
    for p in parcels:
        audit = filter_feasible_lanes_and_vessels(
            db=db_session, commodity="coal", cargo_qty_mt=p["cargo_qty_mt"],
            destination_port_code=p["destination_port_code"]
        )
        feasible_options_by_parcel[p["parcel_id"]] = audit["feasible_candidates"]
        for opt in audit["feasible_candidates"]:
            key = (opt["trade_lane_id"], opt["vessel_class_id"])
            forecasts_by_option.setdefault(key, {h: 16000.0 for h in ENTRY_HORIZONS_DAYS})

    spot_cap_ratio = 0.25
    result = solve_multi_parcel_allocation(
        parcels=parcels,
        feasible_options_by_parcel=feasible_options_by_parcel,
        forecasts_by_option=forecasts_by_option,
        spot_cap_ratio=spot_cap_ratio,
    )

    total_qty = sum(p["cargo_qty_mt"] for p in parcels)
    spot_qty = sum(
        p["cargo_qty_mt"] for p in parcels
        for a in result["assignments"]
        if a["parcel_id"] == p["parcel_id"] and a["contract_type"] == "SPOT"
    )
    assert spot_qty <= spot_cap_ratio * total_qty + 1e-6


def test_laycan_window_gates_entry_horizon(db_session):
    """A parcel whose laycan window only covers the near term should never be
    assigned a far-horizon (e.g. 180d) entry timing."""
    near_start = date.today() + timedelta(days=5)
    near_end = near_start + timedelta(days=10)

    audit = filter_feasible_lanes_and_vessels(
        db=db_session, commodity="coking_coal", cargo_qty_mt=75000.0, destination_port_code="INPRT"
    )
    feasible = audit["feasible_candidates"]
    assert feasible, "expected at least one feasible option for this fixture"

    key = (feasible[0]["trade_lane_id"], feasible[0]["vessel_class_id"])
    forecasts_by_option = {key: {h: 16000.0 for h in ENTRY_HORIZONS_DAYS}}

    parcels = [{
        "parcel_id": "NEAR",
        "cargo_qty_mt": 75000.0,
        "destination_port_code": "INPDP",
        "laycan_start": near_start,
        "laycan_end": near_end,
    }]

    result = solve_multi_parcel_allocation(
        parcels=parcels,
        feasible_options_by_parcel={"NEAR": feasible},
        forecasts_by_option=forecasts_by_option,
    )

    assert len(result["assignments"]) == 1
    assert result["assignments"][0]["horizon_days"] == 7


def test_unfeasible_parcel_is_reported_not_silently_dropped(db_session):
    laycan_start, laycan_end = _laycan()
    parcels = [{
        "parcel_id": "TOO_BIG",
        "cargo_qty_mt": 500000.0,  # exceeds every vessel class's usable capacity
        "destination_port_code": "INPRT",
        "laycan_start": laycan_start,
        "laycan_end": laycan_end,
    }]

    result = solve_multi_parcel_allocation(
        parcels=parcels,
        feasible_options_by_parcel={"TOO_BIG": []},
        forecasts_by_option={},
    )

    assert result["status"] == "NO_FEASIBLE_PARCELS"
    assert result["unassignable_parcels"] == ["TOO_BIG"]
    assert result["assignments"] == []


def test_idle_mitigation_ranks_by_score_and_never_autocommits():
    suggestions = score_idle_mitigation_opportunities(
        idle_vessel_class_name="Panamax",
        idle_position_port_code="INPRT",
        idle_days_available=3.0,
        bunker_consumption_tpd=28.0,
        open_opportunities=[
            {
                "opportunity_id": "GOOD", "cargo_qty_mt": 60000, "origin_port_code": "INPRT",
                "destination_port_code": "CNSHA", "ballast_distance_nm": 300, "transit_days": 12,
                "tce_rate_usd_day": 18000, "laycan_start_in_days": 2, "is_backhaul": True,
            },
            {
                "opportunity_id": "FAR_AND_LATE", "cargo_qty_mt": 40000, "origin_port_code": "AUNCS",
                "destination_port_code": "INPRT", "ballast_distance_nm": 6000, "transit_days": 5,
                "tce_rate_usd_day": 12000, "laycan_start_in_days": 30, "is_backhaul": False,
            },
        ],
        top_n=3,
    )

    assert len(suggestions) == 2
    assert suggestions[0]["score_usd"] >= suggestions[1]["score_usd"]
    assert suggestions[0]["opportunity_id"] == "GOOD"
    for s in suggestions:
        assert s["status"] == "SUGGESTED"
        assert "rationale" in s

    # top_n is respected
    top1 = score_idle_mitigation_opportunities(
        idle_vessel_class_name="Panamax",
        idle_position_port_code="INPRT",
        idle_days_available=3.0,
        bunker_consumption_tpd=28.0,
        open_opportunities=[
            {"opportunity_id": "A", "cargo_qty_mt": 1, "origin_port_code": "X", "destination_port_code": "Y"},
            {"opportunity_id": "B", "cargo_qty_mt": 1, "origin_port_code": "X", "destination_port_code": "Y"},
        ],
        top_n=1,
    )
    assert len(top1) == 1
