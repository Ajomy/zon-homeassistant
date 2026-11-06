"""Config flow tests."""

from __future__ import annotations

import pytest
from aiohttp import ClientConnectionError
from custom_components.zon_forecast.const import (
    API_URL,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from .payload import (
    NOT_CONFIGURED,
    SUCCESS_HEADERS,
    UNAUTHORIZED,
    UNAVAILABLE,
    forecast_body,
)


async def test_user_flow_creates_entry(hass, aioclient_mock) -> None:
    """A valid key is checked and stored, and the system id is the unique id."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "  test-key  "}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Zon Forecast"
    assert result["data"][CONF_API_KEY] == "test-key"
    assert result["options"][CONF_UPDATE_INTERVAL] == 30
    entry = result["result"]
    assert entry.unique_id == "sys_1"
    assert entry.state is ConfigEntryState.LOADED

    method, url, _data, headers = aioclient_mock.mock_calls[0]
    assert method.lower() == "get"
    assert str(url) == API_URL
    assert headers["Authorization"] == "Bearer test-key"
    assert "test-key" not in str(url)


async def test_duplicate_system_aborts(hass, aioclient_mock) -> None:
    """The same system_id cannot be added twice."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "other-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (401, UNAUTHORIZED, "invalid_auth"),
        (503, UNAVAILABLE, "unavailable"),
    ],
)
async def test_user_flow_http_errors(hass, aioclient_mock, status, body, error) -> None:
    """401 and 503 keep the form open with a specific error."""
    aioclient_mock.get(API_URL, status=status, json=body)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == error


async def test_user_flow_not_configured_lists_missing(hass, aioclient_mock) -> None:
    """409 surfaces the missing enum values from the body."""
    aioclient_mock.get(API_URL, status=409, json=NOT_CONFIGURED)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    assert result["errors"]["base"] == "not_configured"
    missing = result["description_placeholders"]["missing"]
    assert "location" in missing
    assert "tilt" in missing


async def test_user_flow_cannot_connect(hass, aioclient_mock) -> None:
    """A connection error is not reported as a bad key."""
    aioclient_mock.get(API_URL, exc=ClientConnectionError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    assert result["errors"]["base"] == "cannot_connect"


async def test_options_flow_interval(hass, aioclient_mock) -> None:
    """The options flow changes the interval and rejects anything under 30 minutes."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    created = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    await hass.async_block_till_done()
    entry = created["result"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_UPDATE_INTERVAL: 15}
        )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_UPDATE_INTERVAL: 60}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL] == 60
    assert entry.runtime_data.update_interval.total_seconds() == 60 * 60


async def test_reauth_replaces_key(hass, aioclient_mock) -> None:
    """A rejected key starts reauth, and a new key for the same system is saved."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    created = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    await hass.async_block_till_done()
    entry = created["result"]

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=401, json=UNAUTHORIZED)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert flows
    assert flows[0]["context"]["source"] == "reauth"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        API_URL, json=forecast_body(system_id="sys_1"), headers=SUCCESS_HEADERS
    )
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {CONF_API_KEY: "new-key"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new-key"


async def test_reauth_rejects_other_system(hass, aioclient_mock) -> None:
    """Reauth does not attach a key that belongs to another system."""
    aioclient_mock.get(API_URL, json=forecast_body(), headers=SUCCESS_HEADERS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    created = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    await hass.async_block_till_done()
    entry = created["result"]

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=401, json=UNAUTHORIZED)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    flow_id = hass.config_entries.flow.async_progress()[0]["flow_id"]

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        API_URL, json=forecast_body(system_id="sys_2"), headers=SUCCESS_HEADERS
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_KEY: "other-system"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data[CONF_API_KEY] == "test-key"
