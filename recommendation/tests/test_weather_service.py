from datetime import date, timedelta

from app.services import weather_service
from app.services.weather_service import VoyageWeatherService


class _EmptyQuery:
    def filter(self, *_args):
        return self

    def first(self):
        return None


class _EmptyDb:
    def query(self, *_args):
        return _EmptyQuery()


def test_weather_window_includes_every_selected_laycan_day(monkeypatch):
    """A 15-day inclusive laycan produces a weather point for all 15 dates."""
    monkeypatch.setattr(weather_service, "fetch_live_marine_weather", lambda *_args: None)

    forecast = VoyageWeatherService(_EmptyDb()).get_voyage_weather_forecast(
        origin_port_code="AUNTL",
        destination_port_code="INPDP",
        departure_date=date(2026, 10, 11),
        transit_days=7,
        weather_end_date=date(2026, 10, 25),
    )

    assert forecast["transit_days"] == 14
    assert forecast["weather_end_date"] == "2026-10-25"
    assert [point["date"] for point in forecast["daily_waypoints"]] == [
        f"2026-10-{day:02d}" for day in range(11, 26)
    ]


def test_live_weather_requests_the_exact_selected_date(monkeypatch):
    requested_params = []
    target_date = date.today() + timedelta(days=1)

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "daily": {
                    "time": [target_date.isoformat()],
                    "wave_height_max": [1.7],
                    "wave_direction_dominant": [180],
                    "wind_speed_10m_max": [30],
                }
            }

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, _url, params):
            requested_params.append(params)
            return FakeResponse()

    monkeypatch.setattr(weather_service.httpx, "Client", lambda **_kwargs: FakeClient())

    weather = weather_service.fetch_live_marine_weather(20.0, 86.0, target_date)

    assert weather is not None
    assert len(requested_params) == 2
    for params in requested_params:
        assert params["start_date"] == target_date.isoformat()
        assert params["end_date"] == target_date.isoformat()
        assert "forecast_days" not in params


def test_weather_beyond_live_forecast_horizon_uses_fallback_without_request(monkeypatch):
    monkeypatch.setattr(
        weather_service.httpx,
        "Client",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("API should not be called")),
    )

    weather = weather_service.fetch_live_marine_weather(
        20.0,
        86.0,
        date.today() + timedelta(days=weather_service.OPEN_METEO_FORECAST_HORIZON_DAYS + 1),
    )

    assert weather is None
