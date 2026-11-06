"""Energy dashboard forecast tests."""

from __future__ import annotations

from custom_components.zon_forecast.const import API_URL, DOMAIN
from custom_components.zon_forecast.energy import async_get_solar_forecast
from homeassistant.const import CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .payload import SUCCESS_HEADERS, forecast_body


async def test_solar_forecast_is_keyed_by_period_start(hass, aioclient_mock) -> None:
    """Watt-hours are moved from the API's period end to the period start."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
        unique_id="sys_1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    forecast = await async_get_solar_forecast(hass, entry.entry_id)
    assert forecast is not None
    hours = forecast["wh_hours"]
    # 400 W over the 15 minutes ending 08:15 is 100 Wh, starting 08:00.
    assert hours["2026-11-06T08:00:00+01:00"] == 100
    # 160 W over the 15 minutes ending 10:00 is 40 Wh, starting 09:45.
    assert hours["2026-11-06T09:45:00+01:00"] == 40

    assert await async_get_solar_forecast(hass, "missing") is None
