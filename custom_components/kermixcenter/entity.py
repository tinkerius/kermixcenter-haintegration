"""Base entities for the kermixcenter integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, MODEL
from .coordinator import KermiXCenterDataUpdateCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api import HomeServer
    from .data import KermiXCenterConfigEntry
    from .datapoints import DiscoveredDatapoint

_DEVICE_TYPE_NAMES = {
    0: "Controller",
    2: "Heat pump",
    3: "Heat pump",
    40: "Ventilation",
}


class KermiHomeServerEntity(CoordinatorEntity[KermiXCenterDataUpdateCoordinator]):
    """Entity attached to an X-Center installation ("home server")."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        home_server: HomeServer,
    ) -> None:
        """Initialise for a home server."""
        super().__init__(coordinator)
        self._home_server_id = home_server.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, home_server.id)},
            name=home_server.name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number=home_server.serial or None,
            sw_version=home_server.version or None,
        )

    @property
    def _home_server(self) -> HomeServer | None:
        return self.coordinator.home_servers.get(self._home_server_id)


class KermiSceneEntity(CoordinatorEntity[KermiXCenterDataUpdateCoordinator]):
    """Entity for an X-Center scene, attached to the installation device."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        home_server_id: str,
        scene_id: str,
    ) -> None:
        """Initialise for a scene on a given installation."""
        super().__init__(coordinator)
        self._home_server_id = home_server_id
        self._scene_id = scene_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, home_server_id)})

    @property
    def _scene(self):  # noqa: ANN202 - api.Scene, avoids an import cycle
        return self.coordinator.scenes.get((self._home_server_id, self._scene_id))

    @property
    def available(self) -> bool:
        """Available while the scene is still returned by the portal."""
        return super().available and self._scene is not None


class KermiDatapointEntity(CoordinatorEntity[KermiXCenterDataUpdateCoordinator]):
    """Base entity for a single Kermi datapoint on a device."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        datapoint: DiscoveredDatapoint,
    ) -> None:
        """Initialise for a discovered datapoint."""
        super().__init__(coordinator)
        self._datapoint = datapoint
        self._attr_unique_id = datapoint.unique_id
        self._attr_name = datapoint.suggested_name
        self._attr_entity_registry_enabled_default = datapoint.enabled_default
        model = _DEVICE_TYPE_NAMES.get(datapoint.device_type, "Device")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, datapoint.device_identifier)},
            via_device=(DOMAIN, datapoint.home_server_id),
            name=datapoint.device_name or model,
            manufacturer=MANUFACTURER,
            model=model,
            serial_number=datapoint.device_serial or None,
            sw_version=datapoint.device_sw_version or None,
        )

    @property
    def _config(self):  # noqa: ANN202 - DatapointConfig, avoids an import cycle
        return self._datapoint.config

    async def _async_write(self, value: object) -> None:
        """Write ``value`` (in display units) to this datapoint."""
        await self.coordinator.async_write_datapoint(self._datapoint, value)

    @property
    def available(self) -> bool:
        """Available only when the last poll returned this datapoint."""
        return super().available and self.coordinator.has_value(self._datapoint)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Expose the datapoint's origin for debugging."""
        attrs = {"datapoint_config_id": self._config.id}
        if self._config.well_known_name:
            attrs["well_known_name"] = self._config.well_known_name
        if self._datapoint.menu_path:
            attrs["menu_path"] = " / ".join(self._datapoint.menu_path)
        return attrs


@callback
def async_add_datapoint_entities(
    hass: HomeAssistant,
    entry: KermiXCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: str,
    factory: Callable[[KermiXCenterDataUpdateCoordinator, DiscoveredDatapoint], Entity],
) -> None:
    """Add entities for datapoints now, and again whenever discovery finds more."""
    coordinator = entry.runtime_data.coordinator
    known: set[str] = set()

    @callback
    def _add() -> None:
        new_entities: list[Entity] = []
        for unique_id, datapoint in coordinator.datapoints.items():
            if unique_id in known or datapoint.platform != platform:
                continue
            known.add(unique_id)
            new_entities.append(factory(coordinator, datapoint))
        if new_entities:
            async_add_entities(new_entities)

    _add()
    entry.async_on_unload(
        async_dispatcher_connect(hass, coordinator.signal_new_datapoints, _add)
    )
