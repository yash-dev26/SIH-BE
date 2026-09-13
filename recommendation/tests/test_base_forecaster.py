from datetime import date
import pytest
from app.features.mock_panel_generator import generate_synthetic_training_panel
from app.forecasting.models.lightgbm_quantile import LightGBMQuantileForecaster
from app.forecasting.models.prophet_model import ProphetForecaster
from app.forecasting.models.sarimax_model import SARIMAXForecaster


@pytest.fixture
def panel_data():
    return generate_synthetic_training_panel(num_days=400, seed=42)


def test_lightgbm_quantile_fit_predict(panel_data):
    forecaster = LightGBMQuantileForecaster(target_variable="TCE_rate")
    forecaster.fit(panel_data, trade_lane_id=1, vessel_class_id=3)

    assert forecaster.is_fitted is True

    res = forecaster.predict(
        panel_df=panel_data,
        trade_lane_id=1,
        vessel_class_id=3,
        target_date=date.today(),
        horizon_days=30
    )

    assert res.point_forecast > 0
    assert res.p10 is not None and res.p90 is not None
    assert res.p10 <= res.point_forecast <= res.p90
    assert res.trade_lane_id == 1
    assert res.vessel_class_id == 3
    assert res.rate_unit == "USD_PER_DAY"


def test_sarimax_fit_predict(panel_data):
    forecaster = SARIMAXForecaster(target_variable="TCE_rate")
    forecaster.fit(panel_data, trade_lane_id=1, vessel_class_id=3)

    assert forecaster.is_fitted is True

    res = forecaster.predict(
        panel_df=panel_data,
        trade_lane_id=1,
        vessel_class_id=3,
        target_date=date.today(),
        horizon_days=7
    )

    assert res.point_forecast > 0
    assert res.p10 <= res.point_forecast <= res.p90


