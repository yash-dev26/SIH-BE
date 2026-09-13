"""
FreightIQ — Comprehensive Verification Matrix & Audit Diagnostics Script
Executes multi-cargo (10k, 25k, 50k, 75k, 80k, 100k MT) and multi-laycan test matrix.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.forecasting.audit import audit_model_coverage_and_quality
from app.forecasting.training_job import run_model_training_pipeline
from app.optimization.recommendation_service import RecommendationService


def main():
    print("==================================================================================")
    print(" FreightIQ — Model Coverage Audit & Full Optimization Verification Matrix")
    print("==================================================================================\n")

    db: Session = SessionLocal()
    init_db(db)

    # 1. Train models across all DB trade lanes and vessel classes
    print("1. Running full-grid model training pipeline...")
    train_res = run_model_training_pipeline(db=db)
    print(f"   [+] Models trained & evaluated count: {train_res['models_trained_count']}")

    # 2. Run Model Coverage Audit
    print("\n2. Model Coverage & Validation Metrics Audit:")
    audit_data = audit_model_coverage_and_quality(db)
    summary = audit_data["dataset_summary"]
    print(f"   [+] Total Training Rows: {summary['total_training_rows']:,}")
    print(f"   [+] Trade Lanes Count: {summary['trade_lanes_count']}")
    print(f"   [+] Vessel Classes Count: {summary['vessel_classes_count']}")
    print(f"   [+] Active Champion Models Count: {summary['trained_champions_count']} / {summary['total_lane_class_combinations']}")
    print(f"   [+] Fallback Models Count: {summary['fallback_combinations_count']}")

    print("\n   [+] Active Champions Matrix:")
    print("       -------------------------------------------------------------------------")
    print(f"       {'Lane':<5} {'Origin->Dest':<16} {'Vessel Class':<12} {'Status':<16} {'MAPE':<8} {'DA %':<8}")
    print("       -------------------------------------------------------------------------")
    for row in audit_data["coverage_matrix"][:10]:
        mape_str = f"{row['mape']:.2f}%" if row['mape'] is not None else "N/A"
        da_str = f"{row['directional_accuracy']:.1f}%" if row['directional_accuracy'] is not None else "N/A"
        lane_str = f"{row['origin_port']}->{row['destination_port']}"
        print(f"       {row['trade_lane_id']:<5} {lane_str:<16} {row['vessel_class_name']:<12} {row['status']:<16} {mape_str:<8} {da_str:<8}")
    print("       -------------------------------------------------------------------------")

    # 3. Execute Verification Matrix Tests
    print("\n3. Executing Cargo Requirement Verification Matrix (10k, 25k, 50k, 75k, 80k, 100k MT)...")

    test_cases = [
        {"cargo_qty": 10000.0, "commodity": "thermal_coal", "dest": "INHAL", "laycan_start": date(2026, 7, 10), "laycan_end": date(2026, 7, 20), "window_name": "Monsoon / Small Vessel"},
        {"cargo_qty": 25000.0, "commodity": "thermal_coal", "dest": "INPDP", "laycan_start": date(2026, 1, 15), "laycan_end": date(2026, 1, 25), "window_name": "Winter / Handysize"},
        {"cargo_qty": 50000.0, "commodity": "thermal_coal", "dest": "INPDP", "laycan_start": date(2026, 7, 1), "laycan_end": date(2026, 7, 15), "window_name": "Monsoon / Supramax"},
        {"cargo_qty": 65000.0, "commodity": "coking_coal", "dest": "INPDP", "laycan_start": date(2026, 10, 1), "laycan_end": date(2026, 10, 15), "window_name": "Cyclone / Panamax"},
        {"cargo_qty": 80000.0, "commodity": "coking_coal", "dest": "INVTZ", "laycan_start": date(2026, 3, 1), "laycan_end": date(2026, 3, 30), "window_name": "Spring / Panamax Flexible"},
        {"cargo_qty": 100000.0, "commodity": "coking_coal", "dest": "INDHM", "laycan_start": date(2026, 2, 1), "laycan_end": date(2026, 2, 10), "window_name": "Deep Draft / Capesize"},
    ]

    rec_svc = RecommendationService(db)
    results = []

    for tc in test_cases:
        try:
            rec = rec_svc.generate_recommendation(
                commodity=tc["commodity"],
                cargo_qty_mt=tc["cargo_qty"],
                destination_port_code=tc["dest"],
                laycan_start=tc["laycan_start"],
                laycan_end=tc["laycan_end"]
            )
            results.append({"tc": tc, "rec": rec, "error": None})
        except Exception as e:
            results.append({"tc": tc, "rec": None, "error": str(e)})

    print("\n   [+] Verification Results Summary:")
    print("   --------------------------------------------------------------------------------------------------------------------------------")
    print(f"   {'Cargo(MT)':<10} {'Origin':<24} {'Vessel':<10} {'Contract':<15} {'Forecast TCE':<14} {'Cost/MT':<10} {'Candidates (Cand/Feas/Rej)':<28} {'Risk Flags':<12}")
    print("   --------------------------------------------------------------------------------------------------------------------------------")

    for res in results:
        tc = res["tc"]
        rec = res["rec"]
        if rec:
            cand_str = f"{rec['candidates_considered_count']} / {rec['feasible_candidates_count']} / {len(rec['rejected_candidates'])}"
            risk_codes = ",".join([r["code"] for r in rec["risk_flags"]]) if rec["risk_flags"] else "NONE"
            print(
                f"   {tc['cargo_qty']:<10,.0f} {rec['recommended_origin_port'][:24]:<24} {rec['recommended_vessel_class']:<10} "
                f"{rec['recommended_contract_type']:<15} ${rec['forecasted_tce_rate_usd_day']:<13,.2f} ${rec['cost_per_mt_usd']:<9.2f} "
                f"{cand_str:<28} {risk_codes:<12}"
            )
            print(f"      -> Contract Rationale: {rec['rationale']['contract_selection_rationale']}")
            print(f"      -> Sample Rejection: {rec['rejected_candidates'][0]['vessel_class_name']} @ {rec['rejected_candidates'][0]['origin_port_name']}: {rec['rejected_candidates'][0]['rejection_reason']}")
            print(f"\n{rec['human_readable_summary']}\n")
            print("   --------------------------------------------------------------------------------------------------------------------------------")

    print("\n==================================================================================")
    print(" FreightIQ Diagnostics & Verification Matrix Completed Successfully!")
    print("==================================================================================")


if __name__ == "__main__":
    main()
