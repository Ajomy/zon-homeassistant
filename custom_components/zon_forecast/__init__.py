"""The Zon Forecast integration.

A connector for the public forecast API. It does not calculate production.
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ZonForecastConfigEntry, ZonForecastDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

__all__ = ["ZonForecastConfigEntry"]


async def async_setup_entry(hass: HomeAssistant, entry: ZonForecastConfigEntry) -> bool:
    """Set up Zon Forecast from a config entry."""
    coordinator = ZonForecastDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ZonForecastConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: ZonForecastConfigEntry
) -> None:
    """Reload when the update interval changes."""
    await hass.config_entries.async_reload(entry.entry_id)
