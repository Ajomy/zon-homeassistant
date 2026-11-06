"""Tests for forecast parsing and the values derived from it."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from custom_components.zon_forecast.forecast import ForecastParseError, parse_forecast
from freezegun import freeze_time

from .payload import FROZEN_UTC, forecast_body


def test_parse_required_fields_and_period_end_energy() -> None:
    """A document matching the schema exposes 15-minute period-end watt-hours."""
    with freeze_time(FROZEN_UTC):
        forecast = parse_forecast(forecast_body())

        assert forecast.system_id == "sys_1"
        assert forecast.timezone == "Europe/Amsterdam"
        assert forecast.period_minutes == 15
        assert forecast.scale == "model"
        assert forecast.rate_limit == 60
        assert forecast.rate_remaining == 59
        assert (
            forecast.watts_hourly[datetime.fromisoformat("2026-11-06T09:00:00+01:00")]
            == 700
        )

        end_0815 = datetime.fromisoformat("2026-11-06T08:15:00+01:00")
        assert forecast.wh_period[end_0815] == 100
        period_start = forecast.watt_hours_by_period_start()
        assert period_start[end_0815 - timedelta(minutes=15)] == 100

        assert forecast.energy_production_today == 18000
        assert forecast.energy_production_tomorrow == 9000
        # 09:10 sits in the period that ends at 09:15 (600 W).
        assert forecast.power_production_now == 600
        assert forecast.power_highest_peak_time_today == datetime.fromisoformat(
            "2026-11-06T08:45:00+01:00"
        )
        assert forecast.power_highest_peak_time_tomorrow == datetime.fromisoformat(
            "2026-11-07T08:30:00+01:00"
        )
        # Periods ending 09:15, 09:30, 09:45, and 10:00.
        assert forecast.energy_current_hour == 240
        # Those, plus 10:15 and 10:30.
        assert forecast.energy_production_today_remaining == 265
        # Next clock hour: periods ending 10:15 and 10:30.
        assert forecast.sum_energy_production(1) == 25
        later = datetime(2026, 11, 6, 10, 10, tzinfo=timezone(timedelta(hours=1)))
        assert forecast.power_production_at_time(later) == 100
        # A gap before tomorrow morning is not the current period.
        evening = datetime(2026, 11, 6, 21, 10, tzinfo=timezone(timedelta(hours=1)))
        assert forecast.power_production_at_time(evening) == 0


def test_rejects_naive_timestamps_and_incomplete_message() -> None:
    """Timestamps must carry an offset, and info.system_id is required."""
    naive = forecast_body()
    naive["result"]["watts"] = {"2026-11-06 09:00:00": 10}
    with pytest.raises(ForecastParseError, match="numeric offset"):
        parse_forecast(naive)

    missing = forecast_body()
    del missing["message"]["info"]["system_id"]
    with pytest.raises(ForecastParseError, match="system_id"):
        parse_forecast(missing)

    bad_day = forecast_body()
    bad_day["result"]["watt_hours_day"] = {"2026-11-06T00:00:00+01:00": 10}
    with pytest.raises(ForecastParseError, match="YYYY-MM-DD"):
        parse_forecast(bad_day)


def test_rejects_non_integer_watts() -> None:
    """Series values are integers in the schema."""
    body = forecast_body(watts={"2026-11-06T09:00:00+01:00": 10.5})
    with pytest.raises(ForecastParseError, match="integer"):
        parse_forecast(body)
