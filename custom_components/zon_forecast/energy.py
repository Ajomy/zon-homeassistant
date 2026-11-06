"""Energy dashboard solar forecast for Zon Forecast."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .coordinator import ZonForecastDataUpdateCoordinator


async def async_get_solar_forecast(
    hass: HomeAssistant, config_entry_id: str
) -> dict[str, dict[str, float | int]] | None:
    """Return watt-hours keyed by the start of each 15-minute period."""
    if (entry := hass.config_entries.async_get_entry(config_entry_id)) is None:
        return None
    coordinator = getattr(entry, "runtime_data", None)
    if not isinstance(coordinator, ZonForecastDataUpdateCoordinator):
        return None
    if coordinator.data is None:
        return None

    by_start = coordinator.data.watt_hours_by_period_start()
    return {
        "wh_hours": {
            start.isoformat(): watt_hours for start, watt_hours in by_start.items()
        }
    }
