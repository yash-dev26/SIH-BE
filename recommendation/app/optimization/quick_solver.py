from typing import Any, Dict, List, Tuple
import pulp


def solve_single_cargo_recommendation(
    feasible_options: List[Dict[str, Any]],
    forecasts_map: Dict[Tuple[int, int], float],
    cargo_qty_mt: float
) -> Dict[str, Any]:
    """
    Uses PuLP Linear Programming solver to select the minimum landed cost option
    satisfying vessel DWT, draft limits, parameterized bunker consumption, and forecasted freight rates.
    """
    prob = pulp.LpProblem("Single_Cargo_Optimization", pulp.LpMinimize)

    # Decision variable: x[i] = 1 if option i is selected, 0 otherwise
    x = {i: pulp.LpVariable(f"option_{i}", cat="Binary") for i in range(len(feasible_options))}

    costs = []
    cost_breakdowns = []

    for i, opt in enumerate(feasible_options):
        key = (opt["trade_lane_id"], opt["vessel_class_id"])
        rate_usd_day = forecasts_map.get(key, 16000.0)
        voyage_days = opt["transit_days"] * 2 + 4.0
        
        bunker_tpd = opt.get("bunker_consumption_tpd", 25.0)
        port_dues = opt.get("typical_port_dues_usd", 40000.0)
        
        # Utilization-adjusted fuel rate
        util_pct = min(100.0, (cargo_qty_mt / opt.get("dwt_max", 65000.0)) * 100.0) if opt.get("dwt_max") else 100.0
        effective_bunker_tpd = bunker_tpd * (0.85 + 0.15 * (util_pct / 100.0))
        
        freight_cost = rate_usd_day * voyage_days
        bunker_cost = voyage_days * effective_bunker_tpd * 550.0  # $550/MT VLSFO
        total_landed = freight_cost + bunker_cost + port_dues

        costs.append(total_landed)
        cost_breakdowns.append({
            "freight_cost_usd": round(freight_cost, 2),
            "bunker_cost_usd": round(bunker_cost, 2),
            "port_dues_usd": round(port_dues, 2),
            "total_landed_cost_usd": round(total_landed, 2),
            "cost_per_mt_usd": round(total_landed / cargo_qty_mt, 2),
            "vessel_utilization_pct": round(util_pct, 1)
        })

    # Objective: Minimize total landed cost
    prob += pulp.lpSum([x[i] * costs[i] for i in range(len(feasible_options))])

    # Constraint: Exactly one option selected
    prob += pulp.lpSum([x[i] for i in range(len(feasible_options))]) == 1

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    best_idx = 0
    for i in range(len(feasible_options)):
        if pulp.value(x[i]) and pulp.value(x[i]) > 0.5:
            best_idx = i
            break

    best_opt = feasible_options[best_idx].copy()
    best_opt["expected_total_cost_usd"] = round(costs[best_idx], 2)
    best_opt["cost_per_mt_usd"] = round(costs[best_idx] / cargo_qty_mt, 2)
    best_opt["tce_rate_usd_day"] = round(forecasts_map.get((best_opt["trade_lane_id"], best_opt["vessel_class_id"]), 16000.0), 2)
    best_opt["cost_breakdown"] = cost_breakdowns[best_idx]

    return best_opt
