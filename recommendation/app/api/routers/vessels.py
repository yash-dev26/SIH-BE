from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import TradeLane, VesselClass
from app.deps import get_db
from app.schemas.vessel import TradeLaneResponse, VesselClassResponse

router = APIRouter(prefix="/vessels", tags=["Vessels"])


@router.get("/classes", response_model=List[VesselClassResponse])
def list_vessel_classes(db: Session = Depends(get_db)) -> List[VesselClassResponse]:
    """Lists all reference vessel classes (Handysize/Supramax/Panamax/Capesize) and their physical envelopes."""
    return db.query(VesselClass).order_by(VesselClass.dwt_min).all()


@router.get("/classes/{vessel_class_id}", response_model=VesselClassResponse)
def get_vessel_class(vessel_class_id: int, db: Session = Depends(get_db)) -> VesselClassResponse:
    vclass = db.query(VesselClass).filter(VesselClass.vessel_class_id == vessel_class_id).first()
    if not vclass:
        raise HTTPException(status_code=404, detail=f"Vessel class {vessel_class_id} not found.")
    return vclass


@router.get("/trade-lanes", response_model=List[TradeLaneResponse])
def list_trade_lanes(db: Session = Depends(get_db)) -> List[TradeLaneResponse]:
    """
    Lists the seeded origin->ECI trade lanes (the same lane universe the forecasting and
    recommendation engines operate over). Useful for a frontend to populate a
    trade_lane_id / vessel_class_id picker ahead of calling /forecasts or /scenarios/compare.
    """
    return db.query(TradeLane).order_by(TradeLane.trade_lane_id).all()
