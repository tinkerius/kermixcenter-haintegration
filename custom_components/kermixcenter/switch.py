"""Switch platform for the kermixcenter integration (writable boolean datapoints)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity

from .datapoints import PLATFORM_SWITCH
from .entity import KermiDatapointEntity, async_add_datapoint_entities

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import KermiXCenterConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KermiXCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up writable boolean datapoints."""
    async_add_datapoint_entities(
        hass, entry, async_add_entities, PLATFORM_SWITCH, KermiDatapointSwitch
    )


class KermiDatapointSwitch(KermiDatapointEntity, SwitchEntity):
    """A writable boolean datapoint (DHW enable, quiet mode, party mode, ...)."""

    @property
    def is_on(self) -> bool | None:
        """Return the datapoint's boolean value."""
        value = self.coordinator.value_for(self._datapoint)
        return None if value is None else bool(value)

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Set the datapoint to True."""
        await self._async_write(value=True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Set the datapoint to False."""
        await self._async_write(value=False)
