"""Sensors for the Zon Forecast integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ACCOUNT_URL, DOMAIN
from .coordinator import ZonForecastConfigEntry, ZonForecastDataUpdateCoordinator
from .forecast import Forecast

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ZonForecastSensorDescription(SensorEntityDescription):
    """A forecast sensor and how to read it."""

    value_fn: Callable[[Forecast], Any]


SENSORS: tuple[ZonForecastSensorDescription, ...] = (
    ZonForecastSensorDescription(
        key="energy_production_today",
        translation_key="energy_production_today",
        value_fn=lambda forecast: forecast.energy_production_today,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    ZonForecastSensorDescription(
        key="energy_production_today_remaining",
        translation_key="energy_production_today_remaining",
        value_fn=lambda forecast: forecast.energy_production_today_remaining,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    ZonForecastSensorDescription(
        key="energy_production_tomorrow",
        translation_key="energy_production_tomorrow",
        value_fn=lambda forecast: forecast.energy_production_tomorrow,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    ZonForecastSensorDescription(
        key="power_highest_peak_time_today",
        translation_key="power_highest_peak_time_today",
        value_fn=lambda forecast: forecast.power_highest_peak_time_today,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    ZonForecastSensorDescription(
        key="power_highest_peak_time_tomorrow",
        translation_key="power_highest_peak_time_tomorrow",
        value_fn=lambda forecast: forecast.power_highest_peak_time_tomorrow,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    ZonForecastSensorDescription(
        key="power_production_now",
        translation_key="power_production_now",
        value_fn=lambda forecast: forecast.power_production_now,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    ZonForecastSensorDescription(
        key="power_production_next_hour",
        translation_key="power_production_next_hour",
        value_fn=lambda forecast: forecast.power_production_at_time(
            forecast.now() + timedelta(hours=1)
        ),
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    ZonForecastSensorDescription(
        key="power_production_next_12hours",
        translation_key="power_production_next_12hours",
        value_fn=lambda forecast: forecast.power_production_at_time(
            forecast.now() + timedelta(hours=12)
        ),
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    ZonForecastSensorDescription(
        key="power_production_next_24hours",
        translation_key="power_production_next_24hours",
        value_fn=lambda forecast: forecast.power_production_at_time(
            forecast.now() + timedelta(hours=24)
        ),
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    ZonForecastSensorDescription(
        key="energy_current_hour",
        translation_key="energy_current_hour",
        value_fn=lambda forecast: forecast.energy_current_hour,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    ZonForecastSensorDescription(
        key="energy_next_hour",
        translation_key="energy_next_hour",
        value_fn=lambda forecast: forecast.sum_energy_production(1),
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZonForecastConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the forecast sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ZonForecastSensor(entry.entry_id, coordinator, description)
        for description in SENSORS
    )


class ZonForecastSensor(
    CoordinatorEntity[ZonForecastDataUpdateCoordinator], SensorEntity
):
    """One value from the Zon Forecast response."""

    _attr_has_entity_name = True
    entity_description: ZonForecastSensorDescription

    def __init__(
        self,
        entry_id: str,
        coordinator: ZonForecastDataUpdateCoordinator,
        description: ZonForecastSensorDescription,
    ) -> None:
        """Set the unique id and the service device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Zon Forecast",
            model="Public API",
            name="Solar production forecast",
            configuration_url=ACCOUNT_URL,
        )

    @property
    def native_value(self) -> datetime | StateType:
        """Return the sensor value from the latest forecast."""
        return self.entity_description.value_fn(self.coordinator.data)
