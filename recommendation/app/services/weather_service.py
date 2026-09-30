import concurrent.futures
import math
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.orm import Session

from app.db.models import Port, TradeLane

logger = logging.getLogger(__name__)

# Open-Meteo's free forecast endpoints provide today plus the next 15 days.
# Dates beyond this are handled by the existing deterministic fallback instead
# of issuing requests that the API rejects with HTTP 400.
OPEN_METEO_FORECAST_HORIZON_DAYS = 15


def calculate_haversine_distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Great Circle distance in nautical miles between two lat/lon coordinates."""
    R_nm = 3440.065  # Earth radius in nautical miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R_nm * c


def interpolate_waypoints(
    lat_start: float, lon_start: float, lat_end: float, lon_end: float, num_days: int
) -> List[Dict[str, float]]:
    """
    Interpolate daily lat/lon waypoints along a great circle or linear path between origin and destination.
    Returns a list of dicts: [{'day': 0, 'lat': ..., 'lon': ...}, ...]
    """
    num_days = max(1, num_days)
    waypoints = []

    for d in range(num_days + 1):
        fraction = d / float(num_days)
        lat = lat_start + (lat_end - lat_start) * fraction
        lon = lon_start + (lon_end - lon_start) * fraction
        waypoints.append({"day": d, "lat": round(lat, 4), "lon": round(lon, 4)})

    return waypoints


def _get_sea_state_label(wave_height_m: float, wind_speed_kts: float) -> str:
    if wave_height_m < 0.5:
        return "Calm (Smooth Sea)"
    elif wave_height_m < 1.25:
        return "Slight (Minor Swell)"
    elif wave_height_m < 2.5:
        return "Moderate (Moderate Swell)"
    elif wave_height_m < 4.0:
        return "Rough (High Swell)"
    elif wave_height_m < 6.0:
        return "Very Rough (Heavy Seas)"
    else:
        return "Phenomenal / Storm Seas"


def _generate_fallback_weather(
    day_idx: int,
    lat: float,
    lon: float,
    target_date: date,
    is_monsoon_region: bool = False
) -> Dict[str, Any]:
    """
    Deterministic realistic marine weather generator when live API is unavailable.
    Tailors weather based on geography, month, and day index.
    """
    month = target_date.month
    pseudo_seed = int((abs(lat) * 10 + abs(lon) * 5 + day_idx * 7 + month * 13) % 100)

    if is_monsoon_region and month in [6, 7, 8, 9]:
        base_wave = 2.8 + (pseudo_seed % 25) / 10.0
        base_wind = 22.0 + (pseudo_seed % 18)
        weather_code = "Monsoon Heavy Squall"
    elif is_monsoon_region and month in [10, 11, 5]:
        base_wave = 1.8 + (pseudo_seed % 20) / 10.0
        base_wind = 16.0 + (pseudo_seed % 15)
        weather_code = "Moderate Tropical Swell"
    else:
        base_wave = 0.8 + (pseudo_seed % 15) / 10.0
        base_wind = 10.0 + (pseudo_seed % 12)
        weather_code = "Fair Oceanic Weather"

    wave_height_m = round(base_wave, 2)
    wind_speed_kts = round(base_wind, 1)
    sea_state = _get_sea_state_label(wave_height_m, wind_speed_kts)

    speed_penalty_pct = 0.0
    fuel_penalty_pct = 0.0
    alert = None

    if wave_height_m >= 4.0 or wind_speed_kts >= 30.0:
        speed_penalty_pct = -15.0
        fuel_penalty_pct = 12.0
    elif wave_height_m >= 2.5 or wind_speed_kts >= 20.0:
        speed_penalty_pct = -6.0
        fuel_penalty_pct = 5.0

    return {
        "day": day_idx,
        "date": target_date.isoformat(),
        "lat": lat,
        "lon": lon,
        "wave_height_m": wave_height_m,
        "wave_direction_deg": (180 + pseudo_seed * 3) % 360,
        "wind_speed_kts": wind_speed_kts,
        "wind_direction": ["NE", "E", "SE", "S", "SW", "W", "NW", "N"][pseudo_seed % 8],
        "sea_state": sea_state,
        "weather_condition": weather_code,
        "visibility_km": 10.0 if wave_height_m < 3.5 else 6.0,
        "speed_penalty_pct": speed_penalty_pct,
        "fuel_penalty_pct": fuel_penalty_pct,
        "alert": alert,
        "data_source": "Realistic Marine Simulator (Fallback)",
    }


def fetch_live_marine_weather(
    lat: float, lon: float, target_date: date
) -> Optional[Dict[str, Any]]:
    """
    Fetches real-time marine forecast data from Open-Meteo API for given lat/lon and target date.
    Returns parsed weather dict or None if request fails.
    """
    latest_live_forecast_date = date.today() + timedelta(days=OPEN_METEO_FORECAST_HORIZON_DAYS)
    if target_date > latest_live_forecast_date:
        logger.info(
            "Live marine forecast unavailable for %s; Open-Meteo currently ends at %s. "
            "Using the marine simulator fallback.",
            target_date.isoformat(),
            latest_live_forecast_date.isoformat(),
        )
        return None

    try:
        url = "https://marine-api.open-meteo.com/v1/marine"
        # Query the exact waypoint date rather than a fixed rolling forecast.
        # ``forecast_days=7`` always starts from today, so it silently omits
        # laycan dates outside that seven-day window.  Supplying the requested
        # date range also lets the service ask for every selected laycan day.
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "wave_height_max,wave_direction_dominant,wind_wave_height_max,swell_wave_height_max",
            "timezone": "UTC",
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
        }
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                daily = data.get("daily", {})
                dates = daily.get("time", [])
                date_str = target_date.isoformat()

                if date_str in dates:
                    idx = dates.index(date_str)
                    wave_max = daily.get("wave_height_max", [])[idx] or 1.5
                    wave_dir = daily.get("wave_direction_dominant", [])[idx] or 180

                    wind_speed_kts = 15.0
                    try:
                        w_resp = client.get(
                            "https://api.open-meteo.com/v1/forecast",
                            params={
                                "latitude": lat,
                                "longitude": lon,
                                "daily": "wind_speed_10m_max,weather_code",
                                "timezone": "UTC",
                                "start_date": target_date.isoformat(),
                                "end_date": target_date.isoformat(),
                            },
                        )
                        if w_resp.status_code == 200:
                            w_data = w_resp.json().get("daily", {})
                            w_dates = w_data.get("time", [])
                            if date_str in w_dates:
                                w_idx = w_dates.index(date_str)
                                wind_kmh = w_data.get("wind_speed_10m_max", [])[w_idx] or 25.0
                                wind_speed_kts = round(wind_kmh * 0.539957, 1)
                    except Exception:
                        pass

                    sea_state = _get_sea_state_label(wave_max, wind_speed_kts)
                    speed_penalty = -12.0 if wave_max >= 3.5 else (-5.0 if wave_max >= 2.2 else 0.0)
                    fuel_penalty = 10.0 if wave_max >= 3.5 else (4.0 if wave_max >= 2.2 else 0.0)

                    alert = None
                    if wave_max >= 3.5:
                        alert = f"Open-Meteo Alert: Heavy Sea Swell {wave_max}m on forecast date."
                    elif wave_max >= 2.2:
                        alert = f"Moderate Sea Warning: Wave height {wave_max}m."

                    return {
                        "date": date_str,
                        "lat": lat,
                        "lon": lon,
                        "wave_height_m": round(wave_max, 2),
                        "wave_direction_deg": wave_dir,
                        "wind_speed_kts": wind_speed_kts,
                        "wind_direction": "SW" if lat > 0 else "NW",
                        "sea_state": sea_state,
                        "weather_condition": "Live Marine Weather",
                        "visibility_km": 10.0,
                        "speed_penalty_pct": speed_penalty,
                        "fuel_penalty_pct": fuel_penalty,
                        "alert": alert,
                        "data_source": "Open-Meteo Marine API",
                    }
    except Exception as e:
        logger.debug(f"Open-Meteo API query failed for ({lat}, {lon}): {e}")

    return None


class VoyageWeatherService:
    """Service to compute voyage route waypoints and forecast sea & weather conditions."""

    def __init__(self, db: Session):
        self.db = db

    def get_voyage_weather_forecast(
        self,
        origin_port_code: str,
        destination_port_code: str,
        departure_date: Optional[date] = None,
        transit_days: int = 7,
        weather_end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Build one weather point for every day in the requested weather window.

        ``weather_end_date`` is normally the laycan end date submitted by the
        frontend.  It takes precedence over the route's estimated transit time
        so the timeline covers the complete selected start/end interval.
        """
        if departure_date is None:
            departure_date = date.today()

        if weather_end_date and weather_end_date < departure_date:
            raise ValueError("weather_end_date must be on or after departure_date")

        origin = self.db.query(Port).filter(Port.port_code == origin_port_code).first()
        destination = self.db.query(Port).filter(Port.port_code == destination_port_code).first()

        lat_start = float(origin.latitude) if origin and origin.latitude else 28.6139
        lon_start = float(origin.longitude) if origin and origin.longitude else 77.2090
        lat_end = float(destination.latitude) if destination and destination.latitude else 20.2644
        lon_end = float(destination.longitude) if destination and destination.longitude else 86.6713

        origin_name = origin.port_name if origin else origin_port_code
        dest_name = destination.port_name if destination else destination_port_code

        eci_ports = ["INPDP", "INPRT", "INVTZ", "INDHM", "INGGV", "INHAL", "INGOP", "INSGR", "INMAA"]
        is_monsoon = origin_port_code in eci_ports or destination_port_code in eci_ports

        trade_lane = self.db.query(TradeLane).filter(
            TradeLane.origin_port_code == origin_port_code,
            TradeLane.destination_port_code == destination_port_code
        ).first()

        sea_dist_nm = float(trade_lane.sea_distance_nm) if trade_lane else calculate_haversine_distance_nm(lat_start, lon_start, lat_end, lon_end)
        if weather_end_date:
            transit_days = (weather_end_date - departure_date).days
        elif transit_days <= 0:
            transit_days = max(1, int(round(sea_dist_nm / 300.0)))

        waypoints = interpolate_waypoints(lat_start, lon_start, lat_end, lon_end, num_days=transit_days)

        def _process_waypoint(wp: Dict[str, Any]) -> Dict[str, Any]:
            day_idx = wp["day"]
            target_date = departure_date + timedelta(days=day_idx)

            live_data = fetch_live_marine_weather(wp["lat"], wp["lon"], target_date)
            if live_data:
                day_weather = {**wp, **live_data}
            else:
                day_weather = _generate_fallback_weather(
                    day_idx=day_idx,
                    lat=wp["lat"],
                    lon=wp["lon"],
                    target_date=target_date,
                    is_monsoon_region=is_monsoon,
                )

            if day_idx == 0:
                day_weather["location_name"] = f"Origin: {origin_name}"
            elif day_idx == transit_days:
                day_weather["location_name"] = f"Destination: {dest_name}"
            else:
                day_weather["location_name"] = f"Waypoint Day {day_idx} ({day_weather['lat']}°, {day_weather['lon']}°)"

            return day_weather

        daily_forecasts = []
        CHUNK_SIZE = 3
        for i in range(0, len(waypoints), CHUNK_SIZE):
            chunk = waypoints[i : i + CHUNK_SIZE]
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(CHUNK_SIZE, len(chunk))) as executor:
                futures = [executor.submit(_process_waypoint, wp) for wp in chunk]
                daily_forecasts.extend([f.result() for f in futures])

        max_wave_height = 0.0
        max_wind_speed = 0.0
        total_speed_penalty = 0.0
        total_fuel_penalty = 0.0
        weather_alerts = []

        for day_weather in daily_forecasts:
            max_wave_height = max(max_wave_height, day_weather["wave_height_m"])
            max_wind_speed = max(max_wind_speed, day_weather["wind_speed_kts"])
            total_speed_penalty += day_weather.get("speed_penalty_pct", 0.0)
            total_fuel_penalty += day_weather.get("fuel_penalty_pct", 0.0)

            if day_weather.get("alert"):
                weather_alerts.append(day_weather["alert"])

        avg_speed_penalty = round(total_speed_penalty / max(1, len(waypoints)), 1)
        avg_fuel_penalty = round(total_fuel_penalty / max(1, len(waypoints)), 1)

        delay_hours = round(abs(avg_speed_penalty) * (transit_days * 24.0 / 100.0), 1)

        safety_score = 100
        if max_wave_height >= 4.5:
            safety_score -= 40
        elif max_wave_height >= 3.0:
            safety_score -= 20

        if max_wind_speed >= 35.0:
            safety_score -= 30
        elif max_wind_speed >= 22.0:
            safety_score -= 15

        if is_monsoon and departure_date.month in [6, 7, 8, 9]:
            safety_score -= 15

        safety_score = max(20, safety_score)

        if safety_score >= 80:
            overall_status = "Optimal Sea Conditions"
            status_color = "GREEN"
        elif safety_score >= 55:
            overall_status = "Moderate Sea Swell Caution"
            status_color = "YELLOW"
        else:
            overall_status = "Heavy Weather / Rough Seas Warning"
            status_color = "RED"

        return {
            "origin_port_code": origin_port_code,
            "origin_port_name": origin_name,
            "destination_port_code": destination_port_code,
            "destination_port_name": dest_name,
            "departure_date": departure_date.isoformat(),
            "weather_end_date": (weather_end_date or (departure_date + timedelta(days=transit_days))).isoformat(),
            "transit_days": transit_days,
            "sea_distance_nm": round(sea_dist_nm, 1),
            "overall_status": overall_status,
            "status_color": status_color,
            "safety_score": safety_score,
            "max_wave_height_m": max_wave_height,
            "max_wind_speed_kts": max_wind_speed,
            "estimated_delay_hours": delay_hours,
            "estimated_fuel_surcharge_pct": avg_fuel_penalty,
            "weather_alerts": list(set(weather_alerts)),
            "daily_waypoints": daily_forecasts,
        }
