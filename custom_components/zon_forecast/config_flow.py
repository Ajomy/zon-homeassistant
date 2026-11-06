"""Config flow for the Zon Forecast integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import (
    CannotConnectError,
    InvalidAuthError,
    NotConfiguredError,
    RateLimitError,
    ServiceUnavailableError,
    UnexpectedResponseError,
    ZonForecastClient,
)
from .const import (
    ACCOUNT_URL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    MAX_UPDATE_INTERVAL_MINUTES,
    MIN_UPDATE_INTERVAL_MINUTES,
)
from .coordinator import update_interval_minutes
from .forecast import Forecast

_MISSING_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "system": "solar system",
        "location": "location",
        "timezone": "time zone",
        "azimuth": "azimuth",
        "tilt": "tilt",
        "panel_size": "panel size",
    },
    "nl": {
        "system": "zonnesysteem",
        "location": "locatie",
        "timezone": "tijdzone",
        "azimuth": "azimut",
        "tilt": "helling",
        "panel_size": "paneelvermogen",
    },
}

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


def _missing_text(language: str, missing: list[str]) -> str:
    """Join the 409 ``missing`` values in the active language."""
    labels = _MISSING_LABELS["nl" if language.lower().startswith("nl") else "en"]
    readable = [labels[item] for item in missing if item in labels]
    if readable:
        return ", ".join(readable)
    if language.lower().startswith("nl"):
        return "vereiste systeemgegevens"
    return "required system details"


class ZonForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for an API key and check it against the forecast endpoint."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ZonForecastOptionsFlow:
        """Return the options flow."""
        return ZonForecastOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial API key step."""
        errors: dict[str, str] = {}
        placeholders = {"account_url": ACCOUNT_URL, "missing": ""}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            error, forecast = await self._async_validate(api_key)
            if error is None and forecast is not None:
                await self.async_set_unique_id(forecast.system_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Zon Forecast",
                    data={CONF_API_KEY: api_key},
                    options={
                        CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_MINUTES,
                    },
                )
            errors["base"] = error or "unknown"
            if error == "not_configured":
                placeholders["missing"] = self._pending_missing
        return self.async_show_form(
            step_id="user",
            data_schema=_USER_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start a repair when the saved key is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Accept a replacement API key for the same solar system."""
        errors: dict[str, str] = {}
        placeholders = {"account_url": ACCOUNT_URL, "missing": ""}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            error, forecast = await self._async_validate(api_key)
            if error is None and forecast is not None:
                if entry.unique_id and forecast.system_id != entry.unique_id:
                    return self.async_abort(reason="unique_id_mismatch")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_API_KEY: api_key},
                )
            errors["base"] = error or "unknown"
            if error == "not_configured":
                placeholders["missing"] = self._pending_missing
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_USER_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def _async_validate(self, api_key: str) -> tuple[str | None, Forecast | None]:
        """Check the key. Return an error key, or the forecast."""
        self._pending_missing = ""
        if not api_key:
            return "invalid_auth", None
        client = ZonForecastClient(async_get_clientsession(self.hass), api_key)
        try:
            forecast = await client.async_get_forecast()
        except InvalidAuthError:
            return "invalid_auth", None
        except NotConfiguredError as err:
            self._pending_missing = _missing_text(
                self.hass.config.language, err.missing
            )
            return "not_configured", None
        except RateLimitError:
            return "rate_limited", None
        except ServiceUnavailableError:
            return "unavailable", None
        except CannotConnectError:
            return "cannot_connect", None
        except UnexpectedResponseError:
            return "unknown", None
        return None, forecast


class ZonForecastOptionsFlow(OptionsFlow):
    """Change how often the forecast is requested."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the update interval. The minimum is 30 minutes."""
        if user_input is not None:
            minutes = int(user_input[CONF_UPDATE_INTERVAL])
            return self.async_create_entry(
                title="",
                data={CONF_UPDATE_INTERVAL: minutes},
            )

        current = update_interval_minutes(self.config_entry)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UPDATE_INTERVAL, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL_MINUTES,
                            max=MAX_UPDATE_INTERVAL_MINUTES,
                            step=15,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="min",
                        )
                    )
                }
            ),
        )
