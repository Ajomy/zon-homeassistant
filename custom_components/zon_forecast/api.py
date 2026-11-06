"""HTTP client for ``GET https://zonforecast.com/api/v1/forecast``."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import aiohttp

from .const import API_URL, DEFAULT_RETRY_AFTER_SECONDS, LOGGER
from .forecast import Forecast, ForecastParseError, parse_forecast

_TIMEOUT = aiohttp.ClientTimeout(total=30)

_MISSING_FIELDS = (
    "system",
    "location",
    "timezone",
    "azimuth",
    "tilt",
    "panel_size",
)


class ZonForecastError(Exception):
    """Base error for the Zon Forecast API."""


class InvalidAuthError(ZonForecastError):
    """HTTP 401. The body does not say whether the key is missing or wrong."""

    def __init__(self, text: str, code: int) -> None:
        """Store the error text from the body."""
        super().__init__(text or "Unauthorized")
        self.text = text
        self.code = code


class NotConfiguredError(ZonForecastError):
    """HTTP 409. ``missing`` lists what the stored system still needs."""

    def __init__(self, text: str, missing: list[str]) -> None:
        """Store the error text and the ``missing`` enum values."""
        super().__init__(text or "not configured")
        self.text = text
        self.missing = missing


class RateLimitError(ZonForecastError):
    """HTTP 429. ``retry_after`` is seconds to wait."""

    def __init__(self, retry_after: int) -> None:
        """Store the wait from Retry-After, RateLimit-Reset, or the body."""
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


class CannotConnectError(ZonForecastError):
    """The API host could not be reached."""


class ServiceUnavailableError(ZonForecastError):
    """HTTP 503. Weather or the account store is temporarily unavailable."""

    def __init__(self, text: str) -> None:
        """Store the error text from the body."""
        super().__init__(text or "unavailable")
        self.text = text


class UnexpectedResponseError(ZonForecastError):
    """A status or body this integration cannot use."""


def _header_int(headers: Any, name: str) -> int | None:
    """Return an integer header, or None when it is absent or not an integer."""
    if headers is None:
        return None
    raw = headers.get(name)
    if raw is None:
        return None
    text = str(raw).strip()
    if not text.isdigit():
        return None
    return int(text)


def _json_object(raw: str) -> dict[str, Any] | None:
    """Parse a JSON object. Any other body becomes None."""
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _message(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the ``message`` object when it matches the error schema."""
    if payload is None:
        return None
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    if not isinstance(message.get("text"), str):
        return None
    if message.get("type") not in (None, "error", "success"):
        return None
    return message


def retry_after_seconds(headers: Any, payload: dict[str, Any] | None) -> int:
    """Seconds to wait after HTTP 429.

    Order is the header contract, then the body:
    ``Retry-After``, then ``RateLimit-Reset``, then
    ``message.ratelimit.retry_after``. All three are integer seconds.
    """
    for name in ("Retry-After", "RateLimit-Reset"):
        parsed = _header_int(headers, name)
        if parsed is not None:
            return max(parsed, 1)
    message = _message(payload)
    ratelimit = message.get("ratelimit") if message else None
    if isinstance(ratelimit, dict) and "retry_after" in ratelimit:
        value = ratelimit["retry_after"]
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return max(value, 1)
    return DEFAULT_RETRY_AFTER_SECONDS


def missing_fields(payload: dict[str, Any] | None) -> list[str]:
    """Return the 409 ``missing`` enum values, in the order the API sent them."""
    message = _message(payload)
    if message is None:
        return []
    raw = message.get("missing")
    if not isinstance(raw, list):
        return []
    found: list[str] = []
    for item in raw:
        if isinstance(item, str) and item in _MISSING_FIELDS and item not in found:
            found.append(item)
    return found


def _error_text(payload: dict[str, Any] | None, default: str) -> str:
    """Return ``message.text`` when the body has one."""
    message = _message(payload)
    if message is None:
        return default
    text = message.get("text")
    return text.strip() if isinstance(text, str) and text.strip() else default


def _error_code(payload: dict[str, Any] | None, default: int) -> int:
    """Return ``message.code`` when it is an integer."""
    message = _message(payload)
    if message is None or isinstance(message.get("code"), bool):
        return default
    code = message.get("code")
    if isinstance(code, int):
        return code
    return default


class ZonForecastClient:
    """Call the forecast endpoint with ``Authorization: Bearer``."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        """Store the shared session and the API key."""
        self._session = session
        self._api_key = api_key

    async def async_get_forecast(self) -> Forecast:
        """Fetch and parse the current forecast."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": "home-assistant-zon-forecast",
        }
        try:
            async with self._session.get(
                API_URL,
                headers=headers,
                timeout=_TIMEOUT,
                allow_redirects=False,
            ) as response:
                status = response.status
                response_headers = response.headers
                raw = await response.text()
        except TimeoutError as err:
            raise CannotConnectError("timed out") from err
        except aiohttp.ClientError as err:
            raise CannotConnectError(err.__class__.__name__) from err

        payload = _json_object(raw)
        if status == 401:
            raise InvalidAuthError(
                _error_text(payload, "Unauthorized"), _error_code(payload, 401)
            )
        if status == 409:
            text = _error_text(payload, "System is not configured")
            raise NotConfiguredError(text, missing_fields(payload))
        if status == 429:
            wait = retry_after_seconds(response_headers, payload)
            LOGGER.debug("Zon Forecast rate limit, retry after %s s", wait)
            raise RateLimitError(wait)
        if status == 503:
            raise ServiceUnavailableError(_error_text(payload, "Unavailable"))
        if status != 200:
            raise UnexpectedResponseError(f"HTTP {status}")

        try:
            forecast = parse_forecast(payload)
        except ForecastParseError as err:
            raise UnexpectedResponseError(str(err)) from err

        limit = _header_int(response_headers, "RateLimit-Limit")
        remaining = _header_int(response_headers, "RateLimit-Remaining")
        reset = _header_int(response_headers, "RateLimit-Reset")
        updates: dict[str, int | None] = {}
        if limit is not None:
            updates["rate_limit"] = limit
        if remaining is not None:
            updates["rate_remaining"] = remaining
        if reset is not None:
            updates["rate_reset_seconds"] = reset
        if updates:
            forecast = replace(forecast, **updates)
        return forecast
