"""Polling coordinator for the Zon Forecast API."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    LOGGER,
    MIN_UPDATE_INTERVAL_MINUTES,
)
from .forecast import Forecast

type ZonForecastConfigEntry = ConfigEntry[ZonForecastDataUpdateCoordinator]


def update_interval_minutes(entry: ConfigEntry) -> int:
    """Return the polling interval, never faster than every 30 minutes."""
    raw = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES)
    try:
        minutes = int(raw)
    except (TypeError, ValueError):
        minutes = DEFAULT_UPDATE_INTERVAL_MINUTES
    return max(minutes, MIN_UPDATE_INTERVAL_MINUTES)


class ZonForecastDataUpdateCoordinator(DataUpdateCoordinator[Forecast]):
    """Fetch the forecast no more often than the configured interval.

    A 429 does not call the API again until the wait from Retry-After (or
    RateLimit-Reset, then the body's retry_after) has elapsed. The last
    successful forecast stays available while waiting.
    """

    config_entry: ZonForecastConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ZonForecastConfigEntry) -> None:
        """Create a client and a coordinator for this config entry."""
        self.client = ZonForecastClient(
            async_get_clientsession(hass), entry.data[CONF_API_KEY]
        )
        self._retry_at: datetime | None = None
        self._rate_limit_logged = False
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=update_interval_minutes(entry)),
        )

    async def _async_update_data(self) -> Forecast:
        """Fetch the forecast, or keep the previous one while rate limited."""
        now = dt_util.utcnow()
        if self._retry_at is not None and now < self._retry_at:
            if self.data is not None:
                return self.data
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
                translation_placeholders={
                    "retry_after": str(int((self._retry_at - now).total_seconds()))
                },
            )

        try:
            forecast = await self.client.async_get_forecast()
        except InvalidAuthError as err:
            raise ConfigEntryAuthFailed("API key was rejected") from err
        except RateLimitError as err:
            self._retry_at = now + timedelta(seconds=err.retry_after)
            if not self._rate_limit_logged:
                LOGGER.warning(
                    "Zon Forecast rate limit reached; next request in %s seconds",
                    err.retry_after,
                )
                self._rate_limit_logged = True
            if self.data is not None:
                return self.data
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
                translation_placeholders={"retry_after": str(err.retry_after)},
            ) from err
        except NotConfiguredError as err:
            missing = ", ".join(err.missing) if err.missing else "required details"
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="not_configured",
                translation_placeholders={"missing": missing},
            ) from err
        except ServiceUnavailableError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="unavailable"
            ) from err
        except CannotConnectError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except UnexpectedResponseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="unexpected_response"
            ) from err

        self._retry_at = None
        self._rate_limit_logged = False
        return forecast
