"""Constants for the Zon Forecast integration."""

from __future__ import annotations

import logging

DOMAIN = "zon_forecast"
LOGGER = logging.getLogger(__package__)

API_URL = "https://zonforecast.com/api/v1/forecast"
ACCOUNT_URL = "https://zonforecast.com/account"

CONF_UPDATE_INTERVAL = "update_interval"

# One request every 30 minutes is 2 per hour, well under the 60/hour key limit.
DEFAULT_UPDATE_INTERVAL_MINUTES = 30
MIN_UPDATE_INTERVAL_MINUTES = 30
MAX_UPDATE_INTERVAL_MINUTES = 1440

# Used when a 429 response omits Retry-After. The published limit is hourly.
DEFAULT_RETRY_AFTER_SECONDS = 3600
