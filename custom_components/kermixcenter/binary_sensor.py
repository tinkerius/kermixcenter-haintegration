"""Binary sensor platform for the kermixcenter integration.

Phase 1 exposes a single connectivity sensor per X-Center installation so the
integration has something to show while the datapoint-based entities are being
built out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .entity import KermiXCenterEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import KermiXCenterConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: KermiXCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        KermiXCenterOnlineBinarySensor(coordinator, home_server)
        for home_server in coordinator.data.home_servers.values()
    )


class KermiXCenterOnlineBinarySensor(KermiXCenterEntity, BinarySensorEntity):
    """Reports whether the X-Center home server is reachable by the portal."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "online"

    def __init__(self, coordinator, home_server) -> None:  # noqa: ANN001
        """Initialise the connectivity sensor."""
        super().__init__(coordinator, home_server)
        self._attr_unique_id = f"{home_server.id}_online"

    @property
    def is_on(self) -> bool | None:
        """Return True when the home server is online."""
        home_server = self._home_server
        return None if home_server is None else home_server.is_online
