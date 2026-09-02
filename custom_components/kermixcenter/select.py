"""Select platform for the kermixcenter integration (writable mode datapoints)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity

from .datapoints import PLATFORM_SELECT, select_options
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
    """Set up writable enumerated datapoints."""
    async_add_datapoint_entities(
        hass, entry, async_add_entities, PLATFORM_SELECT, KermiDatapointSelect
    )


class KermiDatapointSelect(KermiDatapointEntity, SelectEntity):
    """A writable enumerated datapoint (operating mode, fan level, ...)."""

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        datapoint: DiscoveredDatapoint,
    ) -> None:
        """Resolve the option list for the datapoint."""
        super().__init__(coordinator, datapoint)
        self._attr_options = select_options(datapoint.config)

    @property
    def current_option(self) -> str | None:
        """Return the label for the current value."""
        value = self.coordinator.value_for(self._datapoint)
        return None if value is None else self._config.label_for(value)

    async def async_select_option(self, option: str) -> None:
        """Write the value whose label matches ``option``."""
        for raw, label in self._config.possible_values.items():
            if label == option:
                await self._async_write(int(raw))
                return
