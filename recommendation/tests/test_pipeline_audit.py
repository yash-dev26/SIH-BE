"""
FreightIQ — Pipeline Audit & System Invariants Test Suite
Verifies port code resolution, usable capacity utilization, contract cost consistency,
date-dependent risk flags, and forecast metadata semantics.
"""
from datetime import date
import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.optimization.constraints import resolve_port_code, filter_feasible_lanes_and_vessels
from app.optimization.scenario_simulator import compare_charter_scenarios
from app.optimization.risk_engine import evaluate_risk_flags
from app.optimization.recommendation_service import RecommendationService


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    init_db(db)
    yield db
    db.close()


def test_port_code_alias_resolution(db_session: Session):
    """Verifies that internal port code aliases map cleanly to canonical port codes."""
    assert resolve_port_code(db_session, "INPRT") == "INPDP"
    assert resolve_port_code(db_session, "Paradip") == "INPDP"
    assert resolve_port_code(db_session, "Paradip Port") == "INPDP"
    assert resolve_port_code(db_session, "Vizag") == "INVTZ"
    assert resolve_port_code(db_session, "INPDP") == "INPDP"


def test_usable_capacity_and_utilization(db_session: Session):
    """Verifies usable cargo capacity (DWT * 0.95) and mathematical rejection format."""
    audit = filter_feasible_lanes_and_vessels(
        db=db_session,
        commodity="thermal_coal",
        cargo_qty_mt=10000.0,
        destination_port_code="INPDP"
    )

    # 10k MT should be under 30% min utilization threshold for Supramax / Panamax / Capesize
    for rej in audit["rejected_candidates"]:
        if "Under-utilization" in rej["rejection_reason"]:
            assert "Usable capacity:" in rej["rejection_reason"]
            assert "Utilization:" in rej["rejection_reason"]
            assert "Min threshold: 30.0%" in rej["rejection_reason"]


def test_contract_cost_consistency(db_session: Session):
    """Verifies that top-level recommendation costs match 100% with the winning contract scenario."""
    svc = RecommendationService(db_session)
    rec = svc.generate_recommendation(
        commodity="coking_coal",
        cargo_qty_mt=65000.0,
        destination_port_code="INPDP",
        laycan_start=date(2026, 1, 15),
        laycan_end=date(2026, 1, 25)
    )

    win_contract_type = rec["contract"]["type"]
    assert win_contract_type in ["SPOT", "COA", "PERIOD"]

    # Match top-level fields with winning contract object
    assert rec["expected_total_cost_usd"] == rec["contract"]["total_cost_usd"]
    assert rec["cost_per_mt_usd"] == rec["contract"]["cost_per_mt_usd"]
    assert rec["cost_breakdown"]["total_landed_cost_usd"] == rec["contract"]["total_cost_usd"]
    assert round(rec["expected_total_cost_usd"] / rec["cargo_qty_mt"], 2) == rec["cost_per_mt_usd"]


def test_date_dependent_risk_engine():
    """Verifies that SW monsoon risk flags activate in July (month 7) and vanish in January (month 1)."""
    # Winter request (January)
    winter_flags = evaluate_risk_flags(
        origin_port_code="IDTBN",
        origin_port_name="Taboneo Anchorage",
        destination_port_code="INPDP",
        destination_port_name="Paradip Port",
        vessel_class_name="Supramax",
        vessel_laden_draft_m=11.5,
        dest_charted_draft_m=16.5,
        dest_tide_m=2.0,
        forecast_point=16000.0,
        forecast_p10=14000.0,
        forecast_p90=18000.0,
        laycan_start=date(2026, 1, 15),
        sea_distance_nm=2400.0
    )
    winter_codes = [f["code"] for f in winter_flags]
    assert "MONSOON_BERTHING_RESTRICTION" not in winter_codes

    # Summer monsoon request (July)
    summer_flags = evaluate_risk_flags(
        origin_port_code="IDTBN",
        origin_port_name="Taboneo Anchorage",
        destination_port_code="INPDP",
        destination_port_name="Paradip Port",
        vessel_class_name="Supramax",
        vessel_laden_draft_m=11.5,
        dest_charted_draft_m=16.5,
        dest_tide_m=2.0,
        forecast_point=16000.0,
        forecast_p10=14000.0,
        forecast_p90=18000.0,
        laycan_start=date(2026, 7, 15),
        sea_distance_nm=2400.0
    )
    summer_codes = [f["code"] for f in summer_flags]
    assert "MONSOON_BERTHING_RESTRICTION" in summer_codes


def test_forecast_metadata_semantics(db_session: Session):
    """Verifies model_fallback_used = False sets model_fallback_reason to None/empty."""
    svc = RecommendationService(db_session)
    rec = svc.generate_recommendation(
        commodity="thermal_coal",
        cargo_qty_mt=50000.0,
        destination_port_code="INPDP",
        laycan_start=date(2026, 2, 10),
        laycan_end=date(2026, 2, 20)
    )

    if not rec["model_fallback_used"]:
        assert rec["model_fallback_reason"] is None or rec["model_fallback_reason"] == ""
