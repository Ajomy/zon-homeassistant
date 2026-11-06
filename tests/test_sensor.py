"""Sensor state tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.zon_forecast.const import API_URL, CONF_UPDATE_INTERVAL, DOMAIN
from freezegun import freeze_time
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .payload import FROZEN_UTC, SUCCESS_HEADERS, forecast_body


def _entity_id(hass, entry_id: str, key: str) -> str:
    """Return the entity id registered for a sensor key."""
    return er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry_id}_{key}")


async def test_sensors_match_forecast_periods(hass, aioclient_mock) -> None:
    """Sensor states come from the API body, not from a local forecast model."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
        options={CONF_UPDATE_INTERVAL: 30},
        unique_id="sys_1",
    )
    entry.add_to_hass(hass)

    with freeze_time(FROZEN_UTC):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        today = hass.states.get(
            _entity_id(hass, entry.entry_id, "energy_production_today")
        )
        remaining = hass.states.get(
            _entity_id(hass, entry.entry_id, "energy_production_today_remaining")
        )
        tomorrow = hass.states.get(
            _entity_id(hass, entry.entry_id, "energy_production_tomorrow")
        )
        current_hour = hass.states.get(
            _entity_id(hass, entry.entry_id, "energy_current_hour")
        )
        next_hour = hass.states.get(
            _entity_id(hass, entry.entry_id, "energy_next_hour")
        )
        power = hass.states.get(
            _entity_id(hass, entry.entry_id, "power_production_now")
        )
        peak = hass.states.get(
            _entity_id(hass, entry.entry_id, "power_highest_peak_time_today")
        )

    assert today.state in {"18000", "18", "18.0"}
    assert remaining.state in {"265", "0.265"}
    assert tomorrow.state in {"9000", "9", "9.0"}
    assert current_hour.state in {"240", "0.24"}
    assert next_hour.state in {"25", "0.025"}
    assert power.state == "600"
    assert power.attributes["unit_of_measurement"] == "W"
    assert datetime.fromisoformat(peak.state) == datetime(
        2026, 11, 6, 7, 45, tzinfo=UTC
    )

    # Rate-limit headers override the same numbers in the body.
    assert entry.runtime_data.data.rate_remaining == 58
    assert entry.runtime_data.data.rate_limit == 60
    assert entry.runtime_data.data.rate_reset_seconds == 1800
    assert entry.runtime_data.update_interval == timedelta(minutes=30)

    disabled = er.async_get(hass).async_get(
        _entity_id(hass, entry.entry_id, "power_production_next_hour")
    )
    assert disabled.disabled_by is er.RegistryEntryDisabler.INTEGRATION
