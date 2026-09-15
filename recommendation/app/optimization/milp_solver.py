"""
OR-Tools CP-SAT multi-parcel, multi-contract, multi-horizon chartering optimizer.

This is the "full solver" half of Phase 4 (Section 3.2 of the spec). `quick_solver.py`
already handles the sub-second, single-parcel LP case used by the dashboard's instant
mode. This module handles the case the plan calls out separately: N parcels solved
*simultaneously*, so cross-parcel tradeoffs that only exist at the portfolio level -
the SpotCapRatio cap and per-port handling-capacity limits - can actually bind. It is
meant to be invoked from an async Celery job (see app/worker.py), never inline on the
request thread.

Sets / decision variables (mirrors Section 3.2 exactly, with one deliberate scoping
simplification noted below):
    k in K   -> cargo parcels
    (v,l)    -> feasible (vessel_class, trade_lane) options, PRE-FILTERED by
                app.optimization.constraints.filter_feasible_lanes_and_vessels
                (draft/LOA/beam/parcel-size are hard structural filters, not solved here)
    c in C   -> contract type: SPOT / SHORT_TERM / COA / PERIOD
    t in T   -> market-entry timing, represented as a forecast horizon in days
                (7/30/90/180) rather than an explicit calendar period grid - this reuses
                the same horizons ForecastingService already trains/serves against, so
                "when to lock in the fixture" maps directly onto "which horizon's
                forecast are we contracting off of", instead of inventing a second,
                unrelated time index.

    x[k,(v,l),c,t] in {0,1}: parcel k shipped via option (v,l), contract c, entered at
                              horizon t.

Objective: minimize total forecasted freight + bunker + port cost across the whole
parcel book (idle/demurrage terms are handled by the complementary
idle_mitigation.py heuristic per Section 3.3, not folded into this snapshot assignment
model, since idle-day accounting requires a real multi-period vessel schedule that
this MVP does not yet maintain).

Constraints implemented:
    1. Demand satisfaction  - every parcel with >=1 feasible option is shipped exactly once.
    6. Laycan compliance    - an entry horizon is only offered to a parcel if the resulting
                              entry window overlaps that parcel's [laycan_start, laycan_end].
    9. SpotCapRatio         - total cargo qty committed to SPOT <= spot_cap_ratio * total cargo qty.
    5. Port throughput cap  - total cargo qty entering a destination port within a given
                              entry-horizon bucket <= that port's handling capacity for
                              a window of that length (cargo_handling_rate_mt_per_day * horizon_days).

Constraints 2/3/4 (draft, LOA/beam, parcel-size) are enforced upstream as a hard
pre-filter (see constraints.py) and are therefore implicit here: only feasible options
ever reach this solver.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

CONTRACT_TYPES = ["SPOT", "SHORT_TERM", "COA", "PERIOD"]

# Kept identical to scenario_simulator.compare_charter_scenarios' SPOT/COA/PERIOD
# discount factors (SHORT_TERM interpolated between SPOT and COA) so a single-parcel
# MILP answer is economically consistent with the LP quick_solver + scenario simulator.
CONTRACT_RATE_MULTIPLIER = {
    "SPOT": 1.00,
    "SHORT_TERM": 0.97,
    "COA": 0.95,
    "PERIOD": 0.90,
}

ENTRY_HORIZONS_DAYS = [7, 30, 90, 180]

BUNKER_PRICE_USD_MT = 550.0
ENTRY_WINDOW_LENGTH_DAYS = 7


def _voyage_days(transit_days: float) -> float:
    return transit_days * 2 + 4.0  # laden + ballast + port berth/loading days, matches quick_solver/scenario_simulator


def _cost_components(
    option: Dict[str, Any],
    contract_type: str,
    forecast_point_usd_day: float,
    cargo_qty_mt: float,
) -> Dict[str, float]:
    voyage_days = _voyage_days(option["transit_days"])
    dwt_max = option.get("dwt_max", 65000.0)
    util_pct = min(100.0, (cargo_qty_mt / dwt_max) * 100.0) if dwt_max else 100.0
    effective_bunker_tpd = option.get("bunker_consumption_tpd", 25.0) * (0.85 + 0.15 * (util_pct / 100.0))

    tce_rate = forecast_point_usd_day * CONTRACT_RATE_MULTIPLIER[contract_type]
    freight_cost = tce_rate * voyage_days
    bunker_cost = voyage_days * effective_bunker_tpd * BUNKER_PRICE_USD_MT
    port_cost = option.get("typical_port_dues_usd", 40000.0)
    total = freight_cost + bunker_cost + port_cost

    return {
        "tce_rate_usd_day": round(tce_rate, 2),
        "voyage_days": round(voyage_days, 1),
        "vessel_utilization_pct": round(util_pct, 1),
        "freight_cost_usd": round(freight_cost, 2),
        "bunker_cost_usd": round(bunker_cost, 2),
        "port_cost_usd": round(port_cost, 2),
        "total_cost_usd": round(total, 2),
    }


def _entry_window(horizon_days: int) -> Tuple[date, date]:
    start = date.today() + timedelta(days=horizon_days)
    end = start + timedelta(days=ENTRY_WINDOW_LENGTH_DAYS)
    return start, end


def _as_date(value: Any) -> Optional[date]:
    """Accepts either a `date` object (in-process call) or an ISO string (Celery-
    serialized call) and normalizes to `date`, since callers may go through either path."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _horizon_within_laycan(horizon_days: int, laycan_start: Optional[date], laycan_end: Optional[date]) -> bool:
    """Section 3.2, constraint 6: a fixture entered at this horizon must fall within
    the parcel's laycan window. If the parcel didn't supply a laycan window, no
    restriction is applied (keeps the solver usable for exploratory/no-laycan requests)."""
    if laycan_start is None or laycan_end is None:
        return True
    window_start, window_end = _entry_window(horizon_days)
    return window_start <= laycan_end and window_end >= laycan_start


def solve_multi_parcel_allocation(
    parcels: List[Dict[str, Any]],
    feasible_options_by_parcel: Dict[str, List[Dict[str, Any]]],
    forecasts_by_option: Dict[Tuple[int, int], Dict[int, float]],
    spot_cap_ratio: float = 0.4,
    port_capacity_mt_per_day: Optional[Dict[str, float]] = None,
    time_limit_seconds: float = 10.0,
) -> Dict[str, Any]:
    """
    Solves the full multi-parcel MILP described above.

    Args:
        parcels: list of {"parcel_id", "cargo_qty_mt", ...}. Only parcel_id and
            cargo_qty_mt are read here; callers should already have filtered out
            parcels with zero feasible options (see recommendation_service.py) or
            they will simply come back as "unassignable" below.
        feasible_options_by_parcel: parcel_id -> list of feasible option dicts, each
            shaped like constraints.filter_feasible_lanes_and_vessels()'s
            `feasible_candidates` entries (must include trade_lane_id, vessel_class_id,
            destination_port_code, transit_days, dwt_max, bunker_consumption_tpd,
            typical_port_dues_usd).
        forecasts_by_option: (trade_lane_id, vessel_class_id) -> {horizon_days: point_forecast_usd_day}.
        spot_cap_ratio: Section 3.2 constraint 9 - max share of total cargo qty (by
            weight) that may be committed to SPOT contracts across the whole book.
        port_capacity_mt_per_day: destination_port_code -> cargo_handling_rate_mt_per_day,
            used to build the per-entry-horizon throughput cap (constraint 5). Ports not
            present in this dict are treated as unconstrained.
        time_limit_seconds: CP-SAT wall-clock budget; this is meant to run as a Celery
            job so a generous budget is fine, but we still cap it defensively.

    Returns:
        {
          "status": "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "NO_FEASIBLE_PARCELS",
          "total_cost_usd": float,
          "assignments": [ {parcel_id, trade_lane_id, vessel_class_id, vessel_class_name,
                             origin_port_code, origin_port_name, destination_port_code,
                             contract_type, horizon_days, entry_window_start,
                             entry_window_end, cost_breakdown fields...,
                             rationale: {binding_constraints, alternatives_considered}} ],
          "unassignable_parcels": [parcel_id, ...],
          "spot_cap_ratio_applied": float,
        }
    """
    port_capacity_mt_per_day = port_capacity_mt_per_day or {}
    total_cargo_qty = sum(p["cargo_qty_mt"] for p in parcels) or 1.0

    model = cp_model.CpModel()

    # var_key = (parcel_id, option_index, contract_type, horizon_days)
    variables: Dict[Tuple[str, int, str, int], cp_model.IntVar] = {}
    costs: Dict[Tuple[str, int, str, int], Dict[str, float]] = {}
    all_combos_by_parcel: Dict[str, List[Tuple[Tuple[str, int, str, int], Dict[str, Any]]]] = {}

    unassignable_parcels: List[str] = []

    for p in parcels:
        pid = p["parcel_id"]
        options = feasible_options_by_parcel.get(pid, [])
        combos_for_parcel = []
        laycan_start = _as_date(p.get("laycan_start"))
        laycan_end = _as_date(p.get("laycan_end"))

        for oi, opt in enumerate(options):
            key = (opt["trade_lane_id"], opt["vessel_class_id"])
            horizon_forecasts = forecasts_by_option.get(key, {})

            for c in CONTRACT_TYPES:
                for h in ENTRY_HORIZONS_DAYS:
                    if h not in horizon_forecasts:
                        continue
                    if not _horizon_within_laycan(h, laycan_start, laycan_end):
                        continue
                    fc_point = horizon_forecasts[h]
                    cost_info = _cost_components(opt, c, fc_point, p["cargo_qty_mt"])

                    var_key = (pid, oi, c, h)
                    var = model.NewBoolVar(f"x_{pid}_{oi}_{c}_{h}")
                    variables[var_key] = var
                    costs[var_key] = cost_info
                    combos_for_parcel.append((var_key, {**opt, "contract_type": c, "horizon_days": h, **cost_info}))

        all_combos_by_parcel[pid] = combos_for_parcel
        if not combos_for_parcel:
            unassignable_parcels.append(pid)

    solvable_parcels = [p for p in parcels if p["parcel_id"] not in unassignable_parcels]

    if not variables:
        return {
            "status": "NO_FEASIBLE_PARCELS",
            "total_cost_usd": 0.0,
            "assignments": [],
            "unassignable_parcels": unassignable_parcels,
            "spot_cap_ratio_applied": spot_cap_ratio,
        }

    # --- Constraint 1: demand satisfaction -----------------------------------------
    for p in solvable_parcels:
        pid = p["parcel_id"]
        parcel_vars = [variables[vk] for vk, _ in all_combos_by_parcel[pid]]
        model.Add(sum(parcel_vars) == 1)

    # --- Constraint 9: SpotCapRatio (soft-in-spirit, hard-in-formulation cap) ------
    spot_qty_terms = []
    for p in solvable_parcels:
        pid = p["parcel_id"]
        qty_int = int(round(p["cargo_qty_mt"]))
        for var_key, _ in all_combos_by_parcel[pid]:
            _, _, contract_type, _ = var_key
            if contract_type == "SPOT":
                spot_qty_terms.append(qty_int * variables[var_key])
    if spot_qty_terms:
        model.Add(sum(spot_qty_terms) <= int(round(spot_cap_ratio * total_cargo_qty)))

    # --- Constraint 5: destination-port throughput cap per entry-horizon bucket ----
    # Bucket key = (destination_port_code, horizon_days); capacity for a bucket of
    # length `horizon_days` is capacity_mt_per_day * horizon_days.
    throughput_buckets: Dict[Tuple[str, int], List[Any]] = {}
    for p in solvable_parcels:
        pid = p["parcel_id"]
        qty_int = int(round(p["cargo_qty_mt"]))
        for var_key, combo in all_combos_by_parcel[pid]:
            dest_code = combo.get("destination_port_code")
            horizon = combo["horizon_days"]
            if dest_code not in port_capacity_mt_per_day:
                continue
            bucket_key = (dest_code, horizon)
            throughput_buckets.setdefault(bucket_key, []).append(qty_int * variables[var_key])

    for (dest_code, horizon), terms in throughput_buckets.items():
        capacity = port_capacity_mt_per_day[dest_code] * horizon
        model.Add(sum(terms) <= int(round(capacity)))

    # --- Objective: minimize total landed cost across the book --------------------
    model.Minimize(sum(int(round(costs[vk]["total_cost_usd"])) * var for vk, var in variables.items()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    status_name = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": status_name,
            "total_cost_usd": 0.0,
            "assignments": [],
            "unassignable_parcels": [p["parcel_id"] for p in parcels],
            "spot_cap_ratio_applied": spot_cap_ratio,
        }

    assignments = []
    total_cost_usd = 0.0

    for p in solvable_parcels:
        pid = p["parcel_id"]
        combos = all_combos_by_parcel[pid]
        chosen = None
        for var_key, combo in combos:
            if solver.Value(variables[var_key]) == 1:
                chosen = (var_key, combo)
                break
        if chosen is None:
            unassignable_parcels.append(pid)
            continue

        var_key, combo = chosen
        _, _, contract_type, horizon = var_key
        entry_start_date, entry_end_date = _entry_window(horizon)
        entry_start, entry_end = entry_start_date.isoformat(), entry_end_date.isoformat()
        total_cost_usd += combo["total_cost_usd"]

        # Binding-constraint rationale: which of the portfolio-level constraints
        # actually touched this parcel's choice.
        binding_constraints = ["demand_satisfaction"]
        if contract_type == "SPOT" and spot_qty_terms:
            binding_constraints.append(f"spot_cap_ratio<= {spot_cap_ratio:.2f}")
        dest_code = combo.get("destination_port_code")
        if dest_code in port_capacity_mt_per_day:
            binding_constraints.append(f"port_throughput_capacity[{dest_code}@{horizon}d]")

        # Alternatives considered: cheapest 3 other combos for this same parcel.
        other_combos = sorted(
            (c for vk, c in combos if vk != var_key),
            key=lambda c: c["total_cost_usd"],
        )[:3]
        alternatives_considered = [
            {
                "vessel_class_name": c.get("vessel_class_name"),
                "origin_port_name": c.get("origin_port_name"),
                "contract_type": c["contract_type"],
                "horizon_days": c["horizon_days"],
                "total_cost_usd": c["total_cost_usd"],
                "why_rejected": "Higher total landed cost than the selected option.",
            }
            for c in other_combos
        ]

        assignments.append({
            "parcel_id": pid,
            "trade_lane_id": combo["trade_lane_id"],
            "vessel_class_id": combo["vessel_class_id"],
            "vessel_class_name": combo.get("vessel_class_name"),
            "origin_port_code": combo.get("origin_port_code"),
            "origin_port_name": combo.get("origin_port_name"),
            "destination_port_code": dest_code,
            "destination_port_name": combo.get("destination_port_name"),
            "contract_type": contract_type,
            "horizon_days": horizon,
            "entry_window_start": entry_start,
            "entry_window_end": entry_end,
            "tce_rate_usd_day": combo["tce_rate_usd_day"],
            "cost_breakdown": {
                "freight_cost_usd": combo["freight_cost_usd"],
                "bunker_cost_usd": combo["bunker_cost_usd"],
                "port_dues_usd": combo["port_cost_usd"],
                "total_cost_usd": combo["total_cost_usd"],
                "cost_per_mt_usd": round(combo["total_cost_usd"] / p["cargo_qty_mt"], 2),
                "vessel_utilization_pct": combo["vessel_utilization_pct"],
            },
            "total_cost_usd": combo["total_cost_usd"],
            "rationale": {
                "forecast_quantile_used": "point_forecast",
                "binding_constraints": binding_constraints,
                "alternatives_considered": alternatives_considered,
            },
        })

    return {
        "status": status_name,
        "total_cost_usd": round(total_cost_usd, 2),
        "assignments": assignments,
        "unassignable_parcels": sorted(set(unassignable_parcels)),
        "spot_cap_ratio_applied": spot_cap_ratio,
    }


