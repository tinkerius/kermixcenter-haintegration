"""Button platform for the kermixcenter integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .entity import KermiHomeServerEntity

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
    """Set up the rediscovery button."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        KermiRediscoverButton(coordinator, home_server)
        for home_server in coordinator.home_servers.values()
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
