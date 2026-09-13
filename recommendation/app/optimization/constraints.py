from typing import Any, Dict, List, Tuple
from sqlalchemy.orm import Session
from app.db.models import Port, VesselClass, TradeLane

PORT_ALIAS_MAP = {
    "INPRT": "INPDP",
    "PARADIP": "INPDP",
    "PARADIP PORT": "INPDP",
    "VIZAG": "INVTZ",
    "VISAKHAPATNAM": "INVTZ",
    "VISAKHAPATNAM PORT": "INVTZ",
    "GANGAVARAM": "INGGV",
    "DHAMRA": "INDHM",
    "HALDIA": "INHAL",
    "SAGAR": "INSGR",
}


def resolve_port_code(db: Session, code_or_name: str) -> str:
    """Resolves human-readable port names or legacy aliases to standardized internal port codes."""
    if not code_or_name:
        return "INPDP"
    clean = str(code_or_name).strip().upper()
    if clean in PORT_ALIAS_MAP:
        return PORT_ALIAS_MAP[clean]
    port = db.query(Port).filter((Port.port_code == clean) | (Port.port_name.ilike(code_or_name))).first()
    if port:
        return port.port_code
    return clean


def check_port_vessel_feasibility(
    vessel_class: VesselClass,
    port: Port,
    tide_allowance_m: float = 1.0,
    safety_margin_m: float = 0.5
) -> Tuple[bool, List[str]]:
    """
    Checks if a vessel class can physically enter and berth at a port based on
    LOA (length), Beam (width), and Draft (depth) constraints.
    """
    reasons = []
    is_feasible = True

    # 1. LOA Check
    if port.max_loa_m and vessel_class.typical_loa_m:
        if float(vessel_class.typical_loa_m) > float(port.max_loa_m):
            is_feasible = False
            reasons.append(f"Vessel LOA ({vessel_class.typical_loa_m}m) exceeds {port.port_name} max LOA ({port.max_loa_m}m)")

    # 2. Beam Check
    if port.max_beam_m and vessel_class.typical_beam_m:
        if float(vessel_class.typical_beam_m) > float(port.max_beam_m):
            is_feasible = False
            reasons.append(f"Vessel Beam ({vessel_class.typical_beam_m}m) exceeds {port.port_name} max Beam ({port.max_beam_m}m)")

    # 3. Draft Check (Charted draft + tide allowance - safety margin)
    if port.max_draft_charted_m and vessel_class.typical_laden_draft_m:
        effective_draft = float(port.max_draft_charted_m) + float(tide_allowance_m) - float(safety_margin_m)
        if float(vessel_class.typical_laden_draft_m) > effective_draft:
            is_feasible = False
            reasons.append(
                f"Vessel laden draft ({vessel_class.typical_laden_draft_m}m) exceeds {port.port_name} effective draft limit "
                f"({effective_draft:.2f}m = {port.max_draft_charted_m}m charted + {tide_allowance_m}m tide - {safety_margin_m}m safety margin)"
            )

    return is_feasible, reasons


def filter_feasible_lanes_and_vessels(
    db: Session,
    commodity: str,
    cargo_qty_mt: float,
    destination_port_code: str
) -> Dict[str, Any]:
    """
    Filters feasible origin ports, trade lanes, and vessel classes for a given cargo requirement.
    Produces a full candidate audit trail of considered, rejected (with clear mathematical reasons), and feasible candidates.
    """
    canonical_dest_code = resolve_port_code(db, destination_port_code)
    dest_port = db.query(Port).filter(Port.port_code == canonical_dest_code).first()
    if not dest_port:
        raise ValueError(f"Destination port '{destination_port_code}' (code: {canonical_dest_code}) not found in database.")

    vessel_classes = db.query(VesselClass).all()

    # 1. Query trade lanes matching destination port and requested commodity
    trade_lanes = db.query(TradeLane).filter(
        TradeLane.destination_port_code == canonical_dest_code,
        TradeLane.commodity == commodity
    ).all()

    if not trade_lanes:
        # Fallback A: query any trade lane going to destination port
        trade_lanes = db.query(TradeLane).filter(
            TradeLane.destination_port_code == canonical_dest_code
        ).all()

    if not trade_lanes:
        # Fallback B: query all trade lanes in database
        trade_lanes = db.query(TradeLane).all()

    candidates_considered = []
    rejected_candidates = []
    feasible_candidates = []

    for lane in trade_lanes:
        origin_port = db.query(Port).filter(Port.port_code == lane.origin_port_code).first()
        origin_name = origin_port.port_name if origin_port else lane.origin_port_code

        for vclass in vessel_classes:
            # Usable Cargo Capacity model: max_dwt * 0.95 (5% fuel & stores allowance)
            usable_capacity_mt = round(float(vclass.dwt_max) * 0.95, 1)
            utilization_pct = round((cargo_qty_mt / usable_capacity_mt) * 100.0, 1)

            cand_info = {
                "trade_lane_id": lane.trade_lane_id,
                "origin_port_code": lane.origin_port_code,
                "origin_port_name": origin_name,
                "destination_port_code": dest_port.port_code,
                "destination_port_name": dest_port.port_name,
                "vessel_class_id": vclass.vessel_class_id,
                "vessel_class_name": vclass.class_name,
                "dwt_max": float(vclass.dwt_max),
                "usable_capacity_mt": usable_capacity_mt,
                "utilization_pct": utilization_pct,
                "sea_distance_nm": float(lane.sea_distance_nm),
                "transit_days": float(lane.typical_transit_days_laden or (lane.sea_distance_nm / 300.0)),
                "bunker_consumption_tpd": float(vclass.bunker_consumption_tpd),
                "typical_port_dues_usd": float(vclass.typical_port_dues_usd),
            }
            candidates_considered.append(cand_info)

            # Check Parcel Size vs Usable Capacity bounds
            if cargo_qty_mt > usable_capacity_mt:
                rejected_candidates.append({
                    **cand_info,
                    "rejection_reason": f"Cargo: {cargo_qty_mt:,.0f} MT | Usable capacity: {usable_capacity_mt:,.0f} MT | Result: Rejected (Exceeds vessel usable capacity)"
                })
                continue

            min_utilization_capacity_mt = usable_capacity_mt * 0.30
            if cargo_qty_mt < min_utilization_capacity_mt:
                rejected_candidates.append({
                    **cand_info,
                    "rejection_reason": (
                        f"Cargo: {cargo_qty_mt:,.0f} MT | Usable capacity: {usable_capacity_mt:,.0f} MT | "
                        f"Utilization: {utilization_pct:.1f}% | Min threshold: 30.0% | Result: Rejected (Under-utilization)"
                    )
                })
                continue

            # Check Port Physical Feasibility (LOA, Beam, Draft)
            origin_ok, origin_reasons = check_port_vessel_feasibility(vclass, origin_port) if origin_port else (True, [])
            dest_ok, dest_reasons = check_port_vessel_feasibility(vclass, dest_port)

            if not origin_ok:
                rejected_candidates.append({
                    **cand_info,
                    "rejection_reason": f"Origin port restriction ({origin_name}): {'; '.join(origin_reasons)}"
                })
                continue

            if not dest_ok:
                rejected_candidates.append({
                    **cand_info,
                    "rejection_reason": f"Destination port restriction ({dest_port.port_name}): {'; '.join(dest_reasons)}"
                })
                continue

            feasible_candidates.append(cand_info)

    return {
        "candidates_considered_count": len(candidates_considered),
        "feasible_candidates_count": len(feasible_candidates),
        "rejected_candidates": rejected_candidates,
        "feasible_candidates": feasible_candidates,
    }
