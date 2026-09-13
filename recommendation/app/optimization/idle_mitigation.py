"""
Idle Vessel Re-employment Heuristic — Section 3.3.

Complementary to milp_solver.py's demand/cost-side assignment: this module addresses
what happens to a vessel class the plan (or a real fixture) has left idle or ballasting
for a window. It ranks *other* open cargo parcels or backhaul opportunities (e.g. ECI
export cargo for the return leg) that fit the vessel's position and timing.

Per Section 3.3, step 3, this is a recommendation surface only ("Idle Mitigation
Suggestions") — it never auto-commits a fixture, so a human logistics manager stays in
the loop for MVP.
"""

from typing import Any, Dict, List

DEFAULT_BALLAST_SPEED_NM_PER_DAY = 300.0
DEFAULT_BUNKER_PRICE_USD_MT = 550.0
DEFAULT_TOP_N = 3


def _repositioning_cost_usd(
    ballast_distance_nm: float,
    bunker_consumption_tpd: float,
    bunker_price_usd_mt: float = DEFAULT_BUNKER_PRICE_USD_MT,
) -> float:
    """Ballast-leg bunker cost to reposition the idle vessel to the opportunity's load port."""
    ballast_days = ballast_distance_nm / DEFAULT_BALLAST_SPEED_NM_PER_DAY
    return ballast_days * bunker_consumption_tpd * bunker_price_usd_mt


def score_idle_mitigation_opportunities(
    idle_vessel_class_name: str,
    idle_position_port_code: str,
    idle_days_available: float,
    bunker_consumption_tpd: float,
    open_opportunities: List[Dict[str, Any]],
    top_n: int = DEFAULT_TOP_N,
) -> List[Dict[str, Any]]:
    """
    Ranks candidate cargo parcels / backhaul opportunities for a vessel forecast to be
    idle or ballasting, using the plan's scoring rule:

        Score = ExpectedRevenue - (RepositioningCost + OpportunityDelayCost)

    Args:
        idle_vessel_class_name: e.g. "Panamax" — informational, echoed back in output.
        idle_position_port_code: where the vessel currently is / will be idle.
        idle_days_available: how many idle days the vessel already has "for free"
            before it would otherwise sit doing nothing — an opportunity whose laycan
            opens within this window incurs no extra delay cost.
        bunker_consumption_tpd: the idle vessel's class-typical bunker consumption,
            used to price the ballast leg to reach each opportunity.
        open_opportunities: candidate fixtures, each at minimum:
            {
                "opportunity_id": str,
                "cargo_qty_mt": float,
                "origin_port_code": str,
                "destination_port_code": str,
                "ballast_distance_nm": float,   # idle position -> this cargo's load port
                "transit_days": float,          # laden transit days for this opportunity
                "tce_rate_usd_day": float,      # forecasted/contracted rate for this opportunity
                "laycan_start_in_days": float,  # days from now until this opportunity's laycan opens
                "is_backhaul": bool,            # e.g. ECI export leg (iron ore pellets, cement clinker)
            }
        top_n: how many ranked suggestions to return (plan default: top-3).

    Returns:
        Up to `top_n` opportunities, richest-scoring first, each annotated with its
        cost breakdown and a human-readable rationale string ready to render as
        dashboard "Idle Mitigation Suggestions". Never auto-commits anything.
    """
    scored = []

    for opp in open_opportunities:
        transit_days = opp.get("transit_days", 10.0)
        tce_rate = opp.get("tce_rate_usd_day", 15000.0)
        expected_revenue_usd = tce_rate * transit_days

        repositioning_cost_usd = _repositioning_cost_usd(
            ballast_distance_nm=opp.get("ballast_distance_nm", 0.0),
            bunker_consumption_tpd=bunker_consumption_tpd,
        )

        # Extra idle/waiting days beyond what's already "free" (idle_days_available),
        # priced at a half-TCE opportunity-cost rate (the vessel isn't earning, but
        # also isn't burning full operating cost while it waits).
        laycan_wait_days = max(0.0, opp.get("laycan_start_in_days", 0.0))
        excess_wait_days = max(0.0, laycan_wait_days - idle_days_available)
        opportunity_delay_cost_usd = excess_wait_days * tce_rate * 0.5

        score_usd = expected_revenue_usd - (repositioning_cost_usd + opportunity_delay_cost_usd)

        scored.append({
            **opp,
            "vessel_class_name": idle_vessel_class_name,
            "idle_position_port_code": idle_position_port_code,
            "expected_revenue_usd": round(expected_revenue_usd, 2),
            "repositioning_cost_usd": round(repositioning_cost_usd, 2),
            "opportunity_delay_cost_usd": round(opportunity_delay_cost_usd, 2),
            "score_usd": round(score_usd, 2),
            "rationale": (
                f"{'Backhaul' if opp.get('is_backhaul') else 'Open-market'} cargo "
                f"({opp.get('cargo_qty_mt', 0):,.0f} MT, {opp.get('origin_port_code', '?')}\u2192"
                f"{opp.get('destination_port_code', '?')}): expected revenue "
                f"${expected_revenue_usd:,.0f} vs. ${repositioning_cost_usd + opportunity_delay_cost_usd:,.0f} "
                f"repositioning + delay cost \u2192 net score ${score_usd:,.0f}."
            ),
        })

    scored.sort(key=lambda s: s["score_usd"], reverse=True)
    top = scored[:top_n]
    for rank, s in enumerate(top, start=1):
        s["rank"] = rank
        s["status"] = "SUGGESTED"  # recommendation surface only — never auto-committed

    return top
