"""Number platform for the kermixcenter integration (writable setpoints)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity

from .datapoints import PLATFORM_NUMBER, resolve_number
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
    """Set up writable numeric datapoints."""
    async_add_datapoint_entities(
        hass, entry, async_add_entities, PLATFORM_NUMBER, KermiDatapointNumber
    )


class KermiDatapointNumber(KermiDatapointEntity, NumberEntity):
    """A writable numeric datapoint (setpoint, offset, threshold)."""

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        datapoint: DiscoveredDatapoint,
    ) -> None:
        """Resolve range and unit for the datapoint."""
        super().__init__(coordinator, datapoint)
        presentation = resolve_number(datapoint.config)
        self._attr_device_class = presentation.device_class
        self._attr_native_unit_of_measurement = presentation.unit
        self._attr_native_min_value = presentation.native_min
        self._attr_native_max_value = presentation.native_max
        self._attr_native_step = presentation.step

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self.coordinator.value_for(self._datapoint)
        return float(value) if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        """Write a new value."""
        # Integer-typed datapoints must not receive a float.
        payload = round(value) if self._config.datapoint_type == 0 else value
        await self._async_write(payload)
