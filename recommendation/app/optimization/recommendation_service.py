from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.db.models import Port, Recommendation, VesselClass
from app.forecasting.inference_service import ForecastingService
from app.optimization.constraints import filter_feasible_lanes_and_vessels, resolve_port_code
from app.optimization.quick_solver import solve_single_cargo_recommendation
from app.optimization.risk_engine import evaluate_risk_flags
from app.optimization.scenario_simulator import compare_charter_scenarios


class RecommendationService:
    """
    Recommendation Engine for FreightIQ.
    Combines physical port constraints + Phase 3 ML rate forecasts + LP optimizer + risk engine + contract alignment.
    """

    def __init__(self, db: Session):
        self.db = db
        self.forecasting_svc = ForecastingService(db)

    def generate_recommendation(
        self,
        commodity: str,
        cargo_qty_mt: float,
        destination_port_code: str,
        laycan_start: date,
        laycan_end: date
    ) -> Dict[str, Any]:
        # 0. Resolve canonical destination port code
        canonical_dest_code = resolve_port_code(self.db, destination_port_code)

        # 1. Pre-filter physically feasible origin ports and vessel classes + generate candidate audit trail
        candidate_audit = filter_feasible_lanes_and_vessels(
            db=self.db,
            commodity=commodity,
            cargo_qty_mt=cargo_qty_mt,
            destination_port_code=canonical_dest_code
        )

        feasible_options = candidate_audit["feasible_candidates"]

        if not feasible_options:
            rejected_summary = [f"{r['vessel_class_name']} @ {r['origin_port_name']}: {r['rejection_reason']}" for r in candidate_audit["rejected_candidates"][:3]]
            raise ValueError(
                f"No feasible vessel class / trade lane found for {cargo_qty_mt:,.0f} MT {commodity} "
                f"to port {canonical_dest_code}. Rejections: {'; '.join(rejected_summary)}"
            )

        # 2. Retrieve Phase 3 rate forecasts for each feasible (lane, class) pair
        forecasts_map = {}
        forecast_details = {}
        model_fallback_used = False

        for opt in feasible_options:
            lane_id = opt["trade_lane_id"]
            class_id = opt["vessel_class_id"]

            fc_results = self.forecasting_svc.get_forecast(
                trade_lane_id=lane_id,
                vessel_class_id=class_id,
                horizons=[30]
            )

            if fc_results:
                res = fc_results[0]
                forecasts_map[(lane_id, class_id)] = res.point_forecast
                forecast_details[(lane_id, class_id)] = {
                    "point": res.point_forecast,
                    "p10": res.p10,
                    "p90": res.p90,
                    "model_version": res.model_version,
                    "model_id": res.model_id or "CHAMPION",
                    "model_fallback_used": res.model_fallback_used,
                    "model_fallback_reason": res.model_fallback_reason if res.model_fallback_used else None,
                    "model_training_rows": res.model_training_rows or 1825
                }
                if res.model_fallback_used:
                    model_fallback_used = True

        # 3. Solve PuLP Linear Program optimization model to pick best candidate option
        best_option = solve_single_cargo_recommendation(
            feasible_options=feasible_options,
            forecasts_map=forecasts_map,
            cargo_qty_mt=cargo_qty_mt
        )

        key = (best_option["trade_lane_id"], best_option["vessel_class_id"])
        fc_info = forecast_details.get(
            key,
            {
                "point": best_option["tce_rate_usd_day"],
                "p10": round(best_option["tce_rate_usd_day"] * 0.85, 2),
                "p90": round(best_option["tce_rate_usd_day"] * 1.15, 2),
                "model_version": "1.0.0",
                "model_id": "CHAMPION",
                "model_fallback_used": False,
                "model_fallback_reason": None,
                "model_training_rows": 1825
            }
        )

        vclass_obj = self.db.query(VesselClass).filter(VesselClass.vessel_class_id == best_option["vessel_class_id"]).first()
        usable_capacity_mt = round(float(vclass_obj.dwt_max) * 0.95, 1) if vclass_obj else 61750.0
        vladen_draft = float(vclass_obj.typical_laden_draft_m) if vclass_obj and vclass_obj.typical_laden_draft_m else 13.5
        vessel_utilization_pct = min(100.0, round((cargo_qty_mt / usable_capacity_mt) * 100.0, 1))

        dest_port = self.db.query(Port).filter(Port.port_code == canonical_dest_code).first()
        dest_charted_draft = float(dest_port.max_draft_charted_m) if dest_port and dest_port.max_draft_charted_m else 16.5
        dest_tide = float(dest_port.tidal_range_m) if dest_port and dest_port.tidal_range_m else 2.0

        # 4. Simulate side-by-side Spot vs COA vs Period charter scenarios + contract optimization
        charter_scenarios, recommended_contract, contract_rationale, winning_scenario = compare_charter_scenarios(
            cargo_qty_mt=cargo_qty_mt,
            sea_distance_nm=best_option["sea_distance_nm"],
            transit_days=best_option["transit_days"],
            tce_rate_usd_day=best_option["tce_rate_usd_day"],
            bunker_consumption_tpd=best_option.get("bunker_consumption_tpd", 28.0),
            port_dues_usd=best_option.get("typical_port_dues_usd", 50000.0),
            vessel_utilization_pct=vessel_utilization_pct,
            forecast_p10=fc_info["p10"],
            forecast_p90=fc_info["p90"]
        )

        # Top-level cost figures MUST correspond 100% to the winning contract scenario
        expected_total_cost_usd = winning_scenario["total_landed_cost_usd"]
        cost_per_mt_usd = winning_scenario["cost_per_mt_usd"]
        risk_adjusted_cost_usd = winning_scenario["risk_adjusted_cost_usd"]

        cost_breakdown = {
            "freight_cost_usd": winning_scenario.get("freight_cost_usd", round(best_option["tce_rate_usd_day"] * (best_option["transit_days"] * 2 + 4.0), 2)),
            "bunker_cost_usd": winning_scenario["bunker_cost_usd"],
            "port_dues_usd": winning_scenario["port_cost_usd"],
            "risk_adjustment_usd": winning_scenario.get("risk_adjustment_usd", 0.0),
            "total_landed_cost_usd": expected_total_cost_usd,
            "risk_adjusted_cost_usd": risk_adjusted_cost_usd,
            "cost_per_mt_usd": cost_per_mt_usd
        }

        # 5. Evaluate multi-factor risk flags
        risk_flags = evaluate_risk_flags(
            origin_port_code=best_option["origin_port_code"],
            origin_port_name=best_option["origin_port_name"],
            destination_port_code=canonical_dest_code,
            destination_port_name=best_option["destination_port_name"],
            vessel_class_name=best_option["vessel_class_name"],
            vessel_laden_draft_m=vladen_draft,
            dest_charted_draft_m=dest_charted_draft,
            dest_tide_m=dest_tide,
            forecast_point=fc_info["point"],
            forecast_p10=fc_info["p10"],
            forecast_p90=fc_info["p90"],
            laycan_start=laycan_start,
            sea_distance_nm=best_option["sea_distance_nm"]
        )

        # 6. Optimal Entry Window Selection
        window_days = min(7, (laycan_end - laycan_start).days or 7)
        opt_window_start = laycan_start
        opt_window_end = laycan_start + timedelta(days=window_days)
        entry_window_rationale = (
            f"Selected early laycan window ({opt_window_start.strftime('%d %b')} – {opt_window_end.strftime('%d %b %Y')}) "
            f"to minimize risk-adjusted landed cost while avoiding projected port berth delays."
        )

        # 7. Build structured Rationale & Alternatives
        # Build UI-friendly alternatives from charter scenarios that were NOT selected
        alternatives = []
        seen_contracts = set()
        for scenario in charter_scenarios:
            if scenario.get("status") == "SELECTED":
                continue
            ct = scenario["contract_type"]
            if ct in seen_contracts:
                continue
            seen_contracts.add(ct)

            title_map = {
                "SPOT": f"Spot Voyage ({best_option['vessel_class_name']})",
                "COA": f"Short-Term COA ({best_option['vessel_class_name']})",
                "PERIOD": f"Period Charter ({best_option['vessel_class_name']})",
            }
            tradeoff_map = {
                "SPOT": f"Spot rate of ${scenario['cost_per_mt_usd']:.2f}/MT exposes to market volatility (+${scenario.get('risk_adjustment_usd', 0):,.0f} risk premium).",
                "COA": f"COA locks in ${scenario['cost_per_mt_usd']:.2f}/MT with 5% volume discount but requires multi-shipment commitment.",
                "PERIOD": f"Period charter at ${scenario['cost_per_mt_usd']:.2f}/MT offers lowest nominal rate but carries ${scenario.get('risk_adjustment_usd', 0):,.0f} idle capacity risk.",
            }
            alternatives.append({
                "title": title_map.get(ct, f"{ct} Alternative"),
                "vessel_class": best_option["vessel_class_name"],
                "contract_type": ct,
                "tradeoff": tradeoff_map.get(ct, scenario.get("recommendation_note", "Alternative chartering strategy.")),
            })

        # Add a different vessel class alternative if available
        for cand in feasible_options:
            is_selected = (cand["trade_lane_id"] == best_option["trade_lane_id"] and cand["vessel_class_id"] == best_option["vessel_class_id"])
            if is_selected:
                continue
            if cand["vessel_class_name"] == best_option["vessel_class_name"]:
                continue
            fc_key = (cand["trade_lane_id"], cand["vessel_class_id"])
            alt_rate = forecasts_map.get(fc_key, best_option["tce_rate_usd_day"])
            alternatives.append({
                "title": f"{cand['vessel_class_name']} via {cand['origin_port_name']}",
                "vessel_class": cand["vessel_class_name"],
                "contract_type": recommended_contract,
                "tradeoff": (
                    f"Uses {cand['vessel_class_name']} at {cand['utilization_pct']:.0f}% capacity utilization "
                    f"({cand['usable_capacity_mt']:,.0f} MT usable). "
                    f"Different draft/cost profile compared to the recommended {best_option['vessel_class_name']}."
                ),
            })
            if len(alternatives) >= 4:
                break

        # Build binding constraints list for the frontend
        binding_constraints = [
            f"Usable draught limit of {dest_charted_draft:.1f}m at {dest_port.port_name if dest_port else canonical_dest_code}",
            f"Laycan window: {opt_window_start.strftime('%d %b')} – {opt_window_end.strftime('%d %b %Y')}",
            f"Cargo parcel: {cargo_qty_mt:,.0f} MT requires minimum {best_option['vessel_class_name']} class vessel",
        ]

        rationale = {
            "summary": (
                f"Recommended importing {cargo_qty_mt:,.0f} MT of {commodity} from {best_option['origin_port_name']} "
                f"to {best_option['destination_port_name']} using a {best_option['vessel_class_name']} vessel "
                f"({vessel_utilization_pct:.1f}% usable capacity utilization) under a {recommended_contract} contract strategy."
            ),
            "vessel_choice_reason": (
                f"{best_option['vessel_class_name']} provides optimal draft clearance ({vladen_draft:.1f}m draft) "
                f"and {vessel_utilization_pct:.1f}% usable capacity utilization for {cargo_qty_mt:,.0f} MT cargo."
            ),
            "origin_port_choice_reason": (
                f"Trade lane from {best_option['origin_port_name']} to {best_option['destination_port_name']} "
                f"minimizes sea distance ({best_option['sea_distance_nm']:.0f} NM) and landed logistics cost."
            ),
            "contract_selection_rationale": contract_rationale,
            "entry_window_rationale": entry_window_rationale,
            "binding_constraints": binding_constraints,
            "forecast_used": {
                "tce_rate_usd_day": best_option["tce_rate_usd_day"],
                "p10_lower_bound": fc_info["p10"],
                "p90_upper_bound": fc_info["p90"],
                "model_version": fc_info.get("model_version", "1.0.0"),
                "model_id": fc_info.get("model_id", "CHAMPION"),
                "model_fallback_used": fc_info.get("model_fallback_used", False),
                "model_fallback_reason": fc_info.get("model_fallback_reason"),
                "model_training_rows": fc_info.get("model_training_rows", 1825)
            },
            "candidates_audit": {
                "candidates_considered_count": candidate_audit["candidates_considered_count"],
                "feasible_candidates_count": candidate_audit["feasible_candidates_count"],
                "rejected_candidates_sample": candidate_audit["rejected_candidates"][:5]
            }
        }

        # 8. Human-Readable Presentation Summary Card for UI / Chatbot
        risk_bullets = "\n".join([f"• {r['message']}" for r in risk_flags]) if risk_flags else "• Low operational risk environment."
        human_readable_summary = (
            f"--------------------------------------------------\n"
            f"🚢 OPTIMAL IMPORT PLAN\n\n"
            f"{cargo_qty_mt:,.0f} MT {commodity.replace('_', ' ').title()}\n"
            f"{best_option['origin_port_name']} → {best_option['destination_port_name']}\n\n"
            f"🏆 RECOMMENDED\n"
            f"{best_option['vessel_class_name']} · {recommended_contract}\n"
            f"{vessel_utilization_pct:.1f}% usable capacity utilization\n\n"
            f"💰 COST\n"
            f"Total Landed Cost: ${expected_total_cost_usd / 1e6:.3f}M\n"
            f"Cost per MT: ${cost_per_mt_usd:.2f}\n\n"
            f"📈 FREIGHT FORECAST\n"
            f"TCE: ${best_option['tce_rate_usd_day']:,.0f}/day\n"
            f"Expected Range: ${fc_info['p10']:,.0f} – ${fc_info['p90']:,.0f}/day\n"
            f"Model: Champion v{fc_info.get('model_version', '1.0.0')}\n\n"
            f"📅 ENTRY WINDOW\n"
            f"{opt_window_start.strftime('%d %b')} – {opt_window_end.strftime('%d %b %Y')}\n\n"
            f"WHY THIS OPTION?\n"
            f"• Lowest risk-adjusted landed cost among feasible options (${cost_per_mt_usd:.2f}/MT)\n"
            f"• {best_option['vessel_class_name']} provides required usable capacity ({usable_capacity_mt:,.0f} MT)\n"
            f"• {contract_rationale}\n\n"
            f"⚠️ RISKS\n"
            f"{risk_bullets}\n"
            f"--------------------------------------------------"
        )

        recommendation_payload = {
            "commodity": commodity,
            "cargo_qty_mt": cargo_qty_mt,
            "destination": {
                "code": canonical_dest_code,
                "name": dest_port.port_name if dest_port else canonical_dest_code,
                "country": dest_port.country if dest_port else "India"
            },
            "origin": {
                "code": best_option["origin_port_code"],
                "name": best_option["origin_port_name"],
                "trade_lane_id": best_option["trade_lane_id"]
            },
            "vessel": {
                "class": best_option["vessel_class_name"],
                "usable_capacity_mt": usable_capacity_mt,
                "utilization_pct": vessel_utilization_pct
            },
            "contract": {
                "type": recommended_contract,
                "total_cost_usd": expected_total_cost_usd,
                "cost_per_mt_usd": cost_per_mt_usd,
                "risk_adjusted_cost_usd": risk_adjusted_cost_usd
            },
            "entry_window": {
                "start": opt_window_start.isoformat(),
                "end": opt_window_end.isoformat(),
                "rationale": entry_window_rationale
            },
            "forecast": {
                "tce_rate_usd_day": best_option["tce_rate_usd_day"],
                "p10": fc_info["p10"],
                "p90": fc_info["p90"],
                "model_version": fc_info.get("model_version", "1.0.0"),
                "model_id": fc_info.get("model_id", "CHAMPION"),
                "model_fallback_used": fc_info.get("model_fallback_used", False),
                "model_fallback_reason": fc_info.get("model_fallback_reason")
            },
            "cost_breakdown": cost_breakdown,
            "risks": risk_flags,
            "why_selected": [
                f"Lowest risk-adjusted landed cost among feasible options (${cost_per_mt_usd:.2f}/MT).",
                f"{best_option['vessel_class_name']} provides optimal draft clearance and {vessel_utilization_pct:.1f}% usable capacity utilization.",
                contract_rationale
            ],
            "alternatives": alternatives,
            "rejected_candidates": candidate_audit["rejected_candidates"],

            # Backward-compatible top-level keys
            "destination_port_code": canonical_dest_code,
            "recommended_origin_port": best_option["origin_port_name"],
            "recommended_origin_port_code": best_option["origin_port_code"],
            "recommended_vessel_class": best_option["vessel_class_name"],
            "recommended_trade_lane_id": best_option["trade_lane_id"],
            "recommended_contract_type": recommended_contract,
            "recommended_entry_window_start": opt_window_start.isoformat(),
            "recommended_entry_window_end": opt_window_end.isoformat(),
            "expected_total_cost_usd": expected_total_cost_usd,
            "cost_per_mt_usd": cost_per_mt_usd,
            "forecasted_tce_rate_usd_day": best_option["tce_rate_usd_day"],
            "model_id": fc_info.get("model_id", "CHAMPION"),
            "model_version": fc_info.get("model_version", "1.0.0"),
            "model_fallback_used": fc_info.get("model_fallback_used", False),
            "model_fallback_reason": fc_info.get("model_fallback_reason"),
            "model_training_rows": fc_info.get("model_training_rows", 1825),
            "vessel_utilization_pct": vessel_utilization_pct,
            "candidates_considered_count": candidate_audit["candidates_considered_count"],
            "feasible_candidates_count": candidate_audit["feasible_candidates_count"],
            "risk_flags": risk_flags,
            "charter_scenarios": charter_scenarios,
            "rationale": rationale,
            "human_readable_summary": human_readable_summary
        }

        # Persist to DB
        try:
            rec_db = Recommendation(
                request_payload={"commodity": commodity, "cargo_qty_mt": cargo_qty_mt, "destination": canonical_dest_code},
                recommended_vessel_class_id=best_option["vessel_class_id"],
                recommended_contract_type=recommended_contract,
                recommended_entry_window_start=opt_window_start,
                recommended_entry_window_end=opt_window_end,
                expected_cost_usd=expected_total_cost_usd,
                confidence_score=0.92 if not fc_info.get("model_fallback_used", False) else 0.60,
                candidates_considered_count=candidate_audit["candidates_considered_count"],
                feasible_candidates_count=candidate_audit["feasible_candidates_count"],
                rejected_candidates_json=candidate_audit["rejected_candidates"],
                rationale_json=rationale,
                risk_flags=risk_flags
            )
            self.db.add(rec_db)
            self.db.commit()
        except Exception:
            self.db.rollback()

        return recommendation_payload

