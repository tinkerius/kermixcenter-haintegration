"""Sensor platform for the kermixcenter integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity

from .datapoints import PLATFORM_SENSOR, resolve_sensor
from .entity import KermiDatapointEntity, async_add_datapoint_entities

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KermiXCenterDataUpdateCoordinator
    from .data import KermiXCenterConfigEntry
    from .datapoints import DiscoveredDatapoint


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KermiXCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kermi datapoint sensors."""
    async_add_datapoint_entities(
        hass, entry, async_add_entities, PLATFORM_SENSOR, KermiDatapointSensor
    )


class KermiDatapointSensor(KermiDatapointEntity, SensorEntity):
    """A numeric, enumerated or text datapoint exposed as a sensor."""

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        datapoint: DiscoveredDatapoint,
    ) -> None:
        """Resolve presentation for the datapoint."""
        super().__init__(coordinator, datapoint)
        presentation = resolve_sensor(datapoint.config)
        self._attr_device_class = presentation.device_class
        self._attr_state_class = presentation.state_class
        self._attr_native_unit_of_measurement = presentation.unit
        self._attr_entity_category = presentation.entity_category
        self._attr_options = presentation.options
        if presentation.icon:
            self._attr_icon = presentation.icon

    @property
    def native_value(self) -> str | float | None:
        """Return the current value, mapped to a label for enums."""
        value = self.coordinator.value_for(self._datapoint)
        if value is None:
            return None
        if self._config.is_enumerated:
            return self._config.label_for(value)
        if self._config.is_string:
            return str(value)
        if isinstance(value, bool):
            return None
        return value
