from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.weather_service import VoyageWeatherService

router = APIRouter(prefix="/weather", tags=["Voyage Marine Weather"])


@router.get("/voyage-forecast")
def get_voyage_weather_forecast(
    origin_port_code: str = Query(..., description="Origin port code e.g. ZARCB, AUHED"),
    destination_port_code: str = Query(..., description="Destination port code e.g. INPDP, INVTZ"),
    departure_date: Optional[date] = Query(None, description="Voyage departure date (YYYY-MM-DD)"),
    transit_days: int = Query(7, description="Estimated voyage transit days (e.g. 7 days)"),
    db: Session = Depends(get_db),
):
    """
    Returns day-by-day marine weather, sea conditions (wave height, wind speed, sea state),
    and voyage risk alerts along the interpolated sea route from origin to destination port.
    """
    svc = VoyageWeatherService(db)
    return svc.get_voyage_weather_forecast(
        origin_port_code=origin_port_code,
        destination_port_code=destination_port_code,
        departure_date=departure_date,
        transit_days=transit_days,
    )


@router.get("/port-current")
def get_port_weather(
    port_code: str = Query(..., description="Port code e.g. INPDP"),
    db: Session = Depends(get_db),
):
    """
    Returns current marine weather forecast at a specific port.
    """
    svc = VoyageWeatherService(db)
    return svc.get_voyage_weather_forecast(
        origin_port_code=port_code,
        destination_port_code=port_code,
        departure_date=date.today(),
        transit_days=1,
    )
