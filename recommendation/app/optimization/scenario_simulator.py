from typing import Any, Dict, List, Tuple


def compare_charter_scenarios(
    cargo_qty_mt: float,
    sea_distance_nm: float,
    transit_days: float,
    tce_rate_usd_day: float,
    bunker_consumption_tpd: float = 28.0,
    port_dues_usd: float = 50000.0,
    vessel_utilization_pct: float = 100.0,
    bunker_price_usd_mt: float = 550.0,
    forecast_p10: float = None,
    forecast_p90: float = None
) -> Tuple[List[Dict[str, Any]], str, str, Dict[str, Any]]:
    """
    Simulates side-by-side voyage economics across Spot, Short-Term COA, and Period Charter.
    Applies partial-loading fuel curves, calculates risk-adjusted costs, and dynamically selects optimal contract.
    Returns: (scenarios, winning_contract_type, rationale_message, winning_scenario_dict)
    """
    total_voyage_days = transit_days * 2 + 4.0  # Laden + Ballast + Port berth/loading days

    # Partial loading fuel consumption adjustment
    effective_bunker_tpd = bunker_consumption_tpd * (0.85 + 0.15 * (min(100.0, vessel_utilization_pct) / 100.0))
    total_bunker_used_mt = total_voyage_days * effective_bunker_tpd
    total_bunker_cost_usd = total_bunker_used_mt * bunker_price_usd_mt

    p10_val = forecast_p10 if forecast_p10 is not None else tce_rate_usd_day * 0.85
    p90_val = forecast_p90 if forecast_p90 is not None else tce_rate_usd_day * 1.15
    spot_volatility_penalty_usd = max(0.0, (p90_val - tce_rate_usd_day) * total_voyage_days * 0.5)

    # Idle capacity risk penalty for multi-month period commitment
    period_idle_risk_penalty_usd = max(0.0, (90.0 - total_voyage_days) * tce_rate_usd_day * 0.08)

    # 1. SPOT Scenario
    spot_freight_usd = tce_rate_usd_day * total_voyage_days
    spot_landed_usd = spot_freight_usd + total_bunker_cost_usd + port_dues_usd
    spot_risk_adjusted_usd = spot_landed_usd + spot_volatility_penalty_usd
    spot_per_mt = spot_landed_usd / cargo_qty_mt

    # 2. SHORT-TERM COA Scenario (5% volume discount, locked rate)
    coa_tce_rate = tce_rate_usd_day * 0.95
    coa_freight_usd = coa_tce_rate * total_voyage_days
    coa_landed_usd = coa_freight_usd + total_bunker_cost_usd + port_dues_usd
    coa_risk_adjusted_usd = coa_landed_usd
    coa_per_mt = coa_landed_usd / cargo_qty_mt

    # 3. PERIOD CHARTER Scenario (10% rate discount, multi-month commitment)
    period_tce_rate = tce_rate_usd_day * 0.90
    period_freight_usd = period_tce_rate * total_voyage_days
    period_landed_usd = period_freight_usd + total_bunker_cost_usd + port_dues_usd
    period_risk_adjusted_usd = period_landed_usd + period_idle_risk_penalty_usd
    period_per_mt = period_landed_usd / cargo_qty_mt

    raw_scenarios = [
        {
            "scenario": "SPOT_SINGLE_VOYAGE",
            "contract_type": "SPOT",
            "tce_rate_usd_day": round(tce_rate_usd_day, 2),
            "total_voyage_days": round(total_voyage_days, 1),
            "freight_cost_usd": round(spot_freight_usd, 2),
            "bunker_cost_usd": round(total_bunker_cost_usd, 2),
            "port_cost_usd": round(port_dues_usd, 2),
            "risk_adjustment_usd": round(spot_volatility_penalty_usd, 2),
            "total_landed_cost_usd": round(spot_landed_usd, 2),
            "cost_per_mt_usd": round(spot_per_mt, 2),
            "risk_adjusted_cost_usd": round(spot_risk_adjusted_usd, 2),
            "recommendation_note": "Spot fixture exposes charterer to spot rate volatility."
        },
        {
            "scenario": "SHORT_TERM_COA",
            "contract_type": "COA",
            "tce_rate_usd_day": round(coa_tce_rate, 2),
            "total_voyage_days": round(total_voyage_days, 1),
            "freight_cost_usd": round(coa_freight_usd, 2),
            "bunker_cost_usd": round(total_bunker_cost_usd, 2),
            "port_cost_usd": round(port_dues_usd, 2),
            "risk_adjustment_usd": 0.0,
            "total_landed_cost_usd": round(coa_landed_usd, 2),
            "cost_per_mt_usd": round(coa_per_mt, 2),
            "risk_adjusted_cost_usd": round(coa_risk_adjusted_usd, 2),
            "recommendation_note": "Locks in 5% volume discount and hedges against spot market volatility."
        },
        {
            "scenario": "PERIOD_CHARTER",
            "contract_type": "PERIOD",
            "tce_rate_usd_day": round(period_tce_rate, 2),
            "total_voyage_days": round(total_voyage_days, 1),
            "freight_cost_usd": round(period_freight_usd, 2),
            "bunker_cost_usd": round(total_bunker_cost_usd, 2),
            "port_cost_usd": round(port_dues_usd, 2),
            "risk_adjustment_usd": round(period_idle_risk_penalty_usd, 2),
            "total_landed_cost_usd": round(period_landed_usd, 2),
            "cost_per_mt_usd": round(period_per_mt, 2),
            "risk_adjusted_cost_usd": round(period_risk_adjusted_usd, 2),
            "recommendation_note": "Lowest nominal rate, but carries multi-month vessel idle commitment risk."
        }
    ]

    # Select winner by min risk_adjusted_cost_usd
    scenarios_sorted = sorted(raw_scenarios, key=lambda s: s["risk_adjusted_cost_usd"])
    best_scenario = scenarios_sorted[0]
    recommended_contract = best_scenario["contract_type"]

    scenarios = []
    for s in raw_scenarios:
        if s["contract_type"] == recommended_contract:
            s["status"] = "SELECTED"
        else:
            s["status"] = "FEASIBLE_NOT_SELECTED"
        scenarios.append(s)

    if recommended_contract == "COA":
        rationale_msg = (
            f"COA selected as optimal contract. While PERIOD has a lower nominal rate "
            f"(${period_per_mt:.2f}/MT vs ${coa_per_mt:.2f}/MT), PERIOD was FEASIBLE — NOT SELECTED because "
            f"it incurs ${period_idle_risk_penalty_usd:,.0f} in idle capacity risk. COA provides lowest risk-adjusted cost (${coa_per_mt:.2f}/MT)."
        )
    elif recommended_contract == "PERIOD":
        rationale_msg = (
            f"PERIOD selected as optimal contract. Offers lowest risk-adjusted landed cost (${period_per_mt:.2f}/MT)."
        )
    else:
        rationale_msg = (
            f"SPOT selected as optimal contract due to favorable short-term spot rates (${spot_per_mt:.2f}/MT)."
        )

    return scenarios, recommended_contract, rationale_msg, best_scenario


