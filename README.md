# Zon Forecast

Custom Home Assistant integration that reads a solar production forecast from the [Zon Forecast](https://zonforecast.com) public API.

The integration is a connector. It does not calculate production, and it does not talk to an inverter. Each update is one request:

`GET https://zonforecast.com/api/v1/forecast`

The API key is sent as `Authorization: Bearer`. It is stored in the Home Assistant config entry. This repository does not contain keys or other secrets.

## Get an API key

1. Sign in at [zonforecast.com](https://zonforecast.com).
2. Open the [Account page](https://zonforecast.com/account).
3. Create an API key, or copy the key that is already listed there.

The key is checked before Home Assistant saves it.

- A rejected key (HTTP 401) asks you to check the key. The API uses the same error body whether the key is missing or wrong.
- An account whose solar system is not ready (HTTP 409) names what is still missing, such as location, time zone, azimuth, tilt, or panel size. Finish that setup on the Account page, then try again.
- A network failure, or a temporary outage (HTTP 503), is reported separately so it is not confused with a bad key.

Each key allows 60 requests per hour. The default polling interval is 30 minutes (2 requests per hour). The options flow will not go below 30 minutes. When the API answers HTTP 429, the integration waits for the `Retry-After` header (seconds) before calling again, and keeps the last forecast while it waits.

## Install

This repository is not in the default HACS store. Add it as a custom repository, or copy the integration by hand. Do not expect a published release.

### HACS

1. In HACS, open Integrations, then the menu, then Custom repositories.
2. Add `https://github.com/Ajomy/zon-homeassistant` as an Integration.
3. Download **Zon Forecast**.
4. Restart Home Assistant.

### Manual

Copy `custom_components/zon_forecast` into the `custom_components` directory of your Home Assistant configuration. Restart Home Assistant.

## Setup

1. Go to Settings, Devices & services, Add integration, and choose **Zon Forecast**.
2. Paste the API key from the Account page.

The integration adds sensors for energy today, energy remaining today, energy tomorrow, energy this hour, energy next hour, power now, and the time of today's and tomorrow's highest power. Power estimates for 1, 12, and 24 hours ahead are created disabled; enable them from the entity settings if you want them.

To show the forecast on the Energy dashboard, open Settings, Dashboards, Energy, add solar production, and choose this integration as the forecast.

The update interval can be changed under Configure on the integration (30 minutes to 24 hours).

## Development

```bash
pip install -r requirements_test.txt
ruff check . && ruff format --check .
pytest
```

Tests use mocked API responses. They do not call zonforecast.com.

## License

MIT. See [LICENSE](LICENSE).
