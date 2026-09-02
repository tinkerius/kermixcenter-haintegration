"""Button platform for the kermixcenter integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .entity import KermiHomeServerEntity, KermiSceneEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api import HomeServer
    from .coordinator import KermiXCenterDataUpdateCoordinator
    from .data import KermiXCenterConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: KermiXCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the rediscovery button and per-scene run buttons."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        KermiRediscoverButton(coordinator, home_server)
        for home_server in coordinator.home_servers.values()
    )
    async_add_entities(
        KermiSceneRunButton(coordinator, hs_id, scene_id)
        for hs_id, scene_id in coordinator.scenes
    )


class KermiRediscoverButton(KermiHomeServerEntity, ButtonEntity):
    """Re-scan a Kermi installation for datapoints that appeared since setup."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "rediscover"

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        home_server: HomeServer,
    ) -> None:
        """Initialise the button."""
        super().__init__(coordinator, home_server)
        self._attr_unique_id = f"{home_server.id}_rediscover"

    async def async_press(self) -> None:
        """Run discovery again (additive only) and refresh."""
        await self.coordinator.async_rediscover()
        await self.coordinator.async_request_refresh()


class KermiSceneRunButton(KermiSceneEntity, ButtonEntity):
    """Force an X-Center scene's actions to run now, ignoring its condition."""

    def __init__(
        self,
        coordinator: KermiXCenterDataUpdateCoordinator,
        home_server_id: str,
        scene_id: str,
    ) -> None:
        """Initialise the scene run button."""
        super().__init__(coordinator, home_server_id, scene_id)
        self._attr_unique_id = f"{home_server_id}_scene_{scene_id}_run"
        scene = self._scene
        base = scene.name if scene else scene_id
        self._attr_name = f"Scene: {base} run now"

    async def async_press(self) -> None:
        """Execute the scene."""
        await self.coordinator.async_execute_scene(self._home_server_id, self._scene_id)
