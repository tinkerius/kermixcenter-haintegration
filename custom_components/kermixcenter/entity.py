"""Base entity for the kermixcenter integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import KermiXCenterDataUpdateCoordinator

if TYPE_CHECKING:
    from .api import HomeServer


class KermiXCenterEntity(CoordinatorEntity[KermiXCenterDataUpdateCoordinator]):
    """Base class for Kermi X-Center entities."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        home_server: HomeServer,
    ) -> None:
        """Initialise the entity for a given home server."""
        super().__init__(coordinator)
        self._home_server_id = home_server.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, home_server.id)},
            name=home_server.name,
            manufacturer=MANUFACTURER,
            model="X-Center",
            serial_number=home_server.serial or None,
            sw_version=home_server.version or None,
        )

    @property
    def _home_server(self) -> HomeServer | None:
        return self.coordinator.data.home_servers.get(self._home_server_id)
