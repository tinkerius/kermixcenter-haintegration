"""Binary sensor platform for the kermixcenter integration.

* one connectivity sensor per X-Center installation,
* one entity per boolean datapoint discovered on a device, and
* one "running" sensor per scene.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .datapoints import PLATFORM_BINARY_SENSOR, resolve_binary_sensor
from .entity import (
    KermiDatapointEntity,
    KermiHomeServerEntity,
    KermiSceneEntity,
    async_add_datapoint_entities,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api import HomeServer
    from .coordinator import KermiXCenterDataUpdateCoordinator
    from .data import KermiXCenterConfigEntry
    from .datapoints import DiscoveredDatapoint


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KermiXCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        KermiOnlineBinarySensor(coordinator, home_server)
        for home_server in coordinator.home_servers.values()
    )
    async_add_datapoint_entities(
        hass,
        entry,
        async_add_entities,
        PLATFORM_BINARY_SENSOR,
        KermiDatapointBinarySensor,
    )
    async_add_entities(
        KermiSceneRunningBinarySensor(coordinator, hs_id, scene_id)
        for hs_id, scene_id in coordinator.scenes
    )


class KermiOnlineBinarySensor(KermiHomeServerEntity, BinarySensorEntity):
    """Whether the portal can currently reach the X-Center home server."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "online"

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        home_server: HomeServer,
    ) -> None:
        """Initialise the connectivity sensor."""
        super().__init__(coordinator, home_server)
        self._attr_unique_id = f"{home_server.id}_online"

    @property
    def is_on(self) -> bool | None:
        """Return True when the home server is online."""
        home_server = self._home_server
        return None if home_server is None else home_server.is_online


class KermiDatapointBinarySensor(KermiDatapointEntity, BinarySensorEntity):
    """A boolean datapoint on a device."""

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        datapoint: DiscoveredDatapoint,
    ) -> None:
        """Resolve the device class for the datapoint."""
        super().__init__(coordinator, datapoint)
        self._attr_device_class = resolve_binary_sensor(datapoint.config)

    @property
    def is_on(self) -> bool | None:
        """Return the datapoint's boolean value."""
        value = self.coordinator.value_for(self._datapoint)
        return None if value is None else bool(value)


class KermiSceneRunningBinarySensor(KermiSceneEntity, BinarySensorEntity):
    """Whether an X-Center scene's actions are currently applied."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        home_server_id: str,
        scene_id: str,
    ) -> None:
        """Initialise the scene running sensor."""
        super().__init__(coordinator, home_server_id, scene_id)
        self._attr_unique_id = f"{home_server_id}_scene_{scene_id}_running"
        scene = self._scene
        base = scene.name if scene else scene_id
        self._attr_name = f"Scene: {base} running"

    @property
    def is_on(self) -> bool | None:
        """Return whether the scene's actions are running."""
        scene = self._scene
        return None if scene is None else scene.action_is_running
