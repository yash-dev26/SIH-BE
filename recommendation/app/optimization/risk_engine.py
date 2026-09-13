from datetime import date
from typing import Any, Dict, List, Optional


def evaluate_risk_flags(
    origin_port_code: str,
    origin_port_name: str,
    destination_port_code: str,
    destination_port_name: str,
    vessel_class_name: str,
    vessel_laden_draft_m: float,
    dest_charted_draft_m: float,
    dest_tide_m: float,
    forecast_point: float,
    forecast_p10: float,
    forecast_p90: float,
    laycan_start: date,
    sea_distance_nm: float,
    avg_waiting_days_load: float = 2.0,
    avg_waiting_days_disch: float = 3.5
) -> List[Dict[str, Any]]:
    """
    Multi-factor contextual risk engine for FreightIQ.
    Evaluates weather/monsoon seasonality, port congestion demurrage, draft safety buffers,
    long-haul transit exposure, and forecast market volatility with dynamic severity levels.
    """
    flags = []
    month = laycan_start.month

    # 1. Weather & Cyclone / Monsoon Seasonality Risk (Bay of Bengal ECI Ports)
    eci_ports = ["INPDP", "INPRT", "INVTZ", "INDHM", "INGGV", "INHAL", "INGOP", "INSGR"]
    if destination_port_code in eci_ports:
        if month in [10, 11, 5]:
            flags.append({
                "code": "CYCLONE_SEASON_WARNING",
                "severity": "WARNING",
                "message": (
                    f"Bay of Bengal cyclone season window during laycan month ({laycan_start.strftime('%B')}). "
                    f"Potential 2-4 day berthing suspensions at {destination_port_name}."
                )
            })
        elif month in [6, 7, 8, 9]:
            flags.append({
                "code": "MONSOON_BERTHING_RESTRICTION",
                "severity": "INFO",
                "message": (
                    f"Southwest monsoon season active at {destination_port_name}. "
                    f"Anchorage lighterage and transshipment operations subject to weather hold."
                )
            })

    # 2. Draft Clearance Safety Margin Risk
    effective_draft = dest_charted_draft_m + dest_tide_m - 0.5  # 0.5m UKC safety margin
    draft_margin = effective_draft - vessel_laden_draft_m
    if draft_margin < 0.5:
        flags.append({
            "code": "CRITICAL_DRAFT_MARGIN",
            "severity": "WARNING" if draft_margin >= 0.2 else "CRITICAL",
            "message": (
                f"Narrow draft clearance ({draft_margin:.2f}m margin) for {vessel_class_name} at {destination_port_name}. "
                f"Requires high-tide window ({dest_tide_m:.1f}m tide allowance) for safe berthing."
            )
        })

    # 3. Port Congestion & Demurrage Risk
    if avg_waiting_days_disch > 3.0:
        estimated_demurrage_usd = avg_waiting_days_disch * (forecast_point * 1.2)
        flags.append({
            "code": "HIGH_PORT_CONGESTION_RISK",
            "severity": "WARNING",
            "message": (
                f"High congestion reported at {destination_port_name} (avg {avg_waiting_days_disch:.1f} waiting days). "
                f"Estimated demurrage exposure: ~${estimated_demurrage_usd:,.0f}."
            )
        })

    # 4. Long-Haul Transit Risk
    transit_days = sea_distance_nm / 300.0
    if transit_days > 20.0:
        flags.append({
            "code": "LONG_HAUL_TRANSIT_EXPOSURE",
            "severity": "INFO",
            "message": (
                f"Long-haul voyage ({sea_distance_nm:,.0f} NM, ~{transit_days:.1f} transit days) from {origin_port_name}. "
                f"Higher bunker fuel price sensitivity."
            )
        })

    # 5. Freight Rate Volatility / Uncertainty Risk
    spread_ratio = (forecast_p90 - forecast_p10) / max(1.0, forecast_point)
    if spread_ratio > 0.30:
        flags.append({
            "code": "HIGH_RATE_VOLATILITY",
            "severity": "WARNING",
            "message": (
                f"High forecast rate volatility ({spread_ratio*100:.1f}% spread between p10 and p90). "
                f"Locking in a COA is recommended over spot exposure."
            )
        })

    return flags
