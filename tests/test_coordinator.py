"""Coordinator polling and rate-limit tests."""

from __future__ import annotations

from datetime import timedelta

from custom_components.zon_forecast.const import (
    API_URL,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from freezegun import freeze_time
from homeassistant.const import CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .payload import (
    NOT_CONFIGURED,
    RATE_LIMIT_HEADERS,
    RATE_LIMITED,
    SUCCESS_HEADERS,
    forecast_body,
)


async def test_interval_cannot_be_faster_than_30_minutes(hass, aioclient_mock) -> None:
    """A stored interval below 30 minutes is still polled at 30 minutes."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
        options={CONF_UPDATE_INTERVAL: 5},
        unique_id="sys_1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval == timedelta(minutes=30)


async def test_rate_limit_waits_for_retry_after(hass, aioclient_mock) -> None:
    """After 429, further refreshes do not call the API until Retry-After."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
        unique_id="sys_1",
    )
    entry.add_to_hass(hass)

    with freeze_time("2026-11-06T08:00:00+00:00") as frozen:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert aioclient_mock.call_count == 1

        aioclient_mock.clear_requests()
        aioclient_mock.get(
            API_URL, status=429, json=RATE_LIMITED, headers=RATE_LIMIT_HEADERS
        )
        await entry.runtime_data.async_refresh()
        assert aioclient_mock.call_count == 1
        assert entry.runtime_data.last_update_success
        assert entry.runtime_data.data.energy_production_today == 18000

        await entry.runtime_data.async_refresh()
        assert aioclient_mock.call_count == 1

        frozen.tick(delta=timedelta(seconds=121))
        aioclient_mock.clear_requests()
        aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
        await entry.runtime_data.async_refresh()
        assert aioclient_mock.call_count == 1


async def test_conflict_marks_update_failed(hass, aioclient_mock) -> None:
    """A later 409 marks the sensors unavailable and keeps the missing fields."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
        unique_id="sys_1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=409, json=NOT_CONFIGURED)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert entry.runtime_data.last_update_success is False


async def test_unload(hass, aioclient_mock) -> None:
    """The entry unloads its sensors."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
        unique_id="sys_1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
