"""Switch platform: writable boolean datapoints and scene enable/disable."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity

from .datapoints import PLATFORM_SWITCH
from .entity import (
    KermiDatapointEntity,
    KermiSceneEntity,
    async_add_datapoint_entities,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KermiXCenterDataUpdateCoordinator
    from .data import KermiXCenterConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KermiXCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up writable boolean datapoints and scene switches."""
    async_add_datapoint_entities(
        hass, entry, async_add_entities, PLATFORM_SWITCH, KermiDatapointSwitch
    )
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        KermiSceneSwitch(coordinator, hs_id, scene_id)
        for hs_id, scene_id in coordinator.scenes
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


class KermiSceneSwitch(KermiSceneEntity, SwitchEntity):
    """Enable or disable an X-Center scene."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        home_server_id: str,
        scene_id: str,
    ) -> None:
        """Initialise the scene switch."""
        super().__init__(coordinator, home_server_id, scene_id)
        self._attr_unique_id = f"{home_server_id}_scene_{scene_id}"
        scene = self._scene
        self._attr_name = f"Scene: {scene.name}" if scene else f"Scene {scene_id}"

    @property
    def is_on(self) -> bool | None:
        """Return whether the scene is enabled."""
        scene = self._scene
        return None if scene is None else scene.enabled

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Enable the scene."""
        await self.coordinator.async_set_scene_enabled(
            self._home_server_id, self._scene_id, enabled=True
        )

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Disable the scene."""
        await self.coordinator.async_set_scene_enabled(
            self._home_server_id, self._scene_id, enabled=False
        )
