from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import Port, VesselClass
from app.deps import get_db
from app.optimization.constraints import check_port_vessel_feasibility, resolve_port_code
from app.schemas.port import PortConstraintsResponse, PortResponse, VesselFeasibilityRow

router = APIRouter(prefix="/ports", tags=["Ports"])


@router.get("", response_model=List[PortResponse])
def list_ports(
    role: Optional[str] = Query(None, description="Filter by port role: LOAD, DISCHARGE, or BOTH"),
    country: Optional[str] = Query(None, description="Filter by country"),
    db: Session = Depends(get_db),
) -> List[PortResponse]:
    """Lists reference ports with their physical constraint data (LOA/beam/draft/tide)."""
    query = db.query(Port)
    if role:
        query = query.filter(Port.role == role.upper())
    if country:
        query = query.filter(Port.country.ilike(country))
    return query.order_by(Port.port_name).all()


@router.get("/{port_id}", response_model=PortResponse)
def get_port(port_id: str, db: Session = Depends(get_db)) -> PortResponse:
    """
    Looks up a single port by its numeric port_id, its UNLOCODE-style port_code, or a
    known alias/name (e.g. 'Paradip', 'INPRT') via the same resolver the recommendation
    engine uses, so the frontend can link straight from a recommendation's port fields.
    """
    port = None
    if port_id.isdigit():
        port = db.query(Port).filter(Port.port_id == int(port_id)).first()
    if port is None:
        canonical_code = resolve_port_code(db, port_id)
        port = db.query(Port).filter(Port.port_code == canonical_code).first()
    if port is None:
        raise HTTPException(status_code=404, detail=f"Port '{port_id}' not found.")
    return port


@router.get("/{port_id}/constraints", response_model=PortConstraintsResponse)
def get_port_constraints(port_id: str, db: Session = Depends(get_db)) -> PortConstraintsResponse:
    """
    Feasibility matrix: for the given port, which vessel classes can physically berth given
    the port's LOA/beam/charted-draft limits (Section 5.1's tide-adjusted effective draft,
    using the port's own tidal_range_m as the tide allowance).
    """
    port = None
    if port_id.isdigit():
        port = db.query(Port).filter(Port.port_id == int(port_id)).first()
    if port is None:
        canonical_code = resolve_port_code(db, port_id)
        port = db.query(Port).filter(Port.port_code == canonical_code).first()
    if port is None:
        raise HTTPException(status_code=404, detail=f"Port '{port_id}' not found.")

    tide_allowance_m = float(port.tidal_range_m) if port.tidal_range_m else 1.0
    rows: List[VesselFeasibilityRow] = []
    for vclass in db.query(VesselClass).order_by(VesselClass.dwt_max).all():
        is_feasible, reasons = check_port_vessel_feasibility(vclass, port, tide_allowance_m=tide_allowance_m)
        rows.append(
            VesselFeasibilityRow(
                vessel_class_id=vclass.vessel_class_id,
                vessel_class_name=vclass.class_name,
                is_feasible=is_feasible,
                reasons=reasons,
            )
        )
    return PortConstraintsResponse(port=port, tide_allowance_m=tide_allowance_m, vessel_feasibility=rows)
