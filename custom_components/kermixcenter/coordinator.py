"""DataUpdateCoordinator for the kermixcenter integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    Device,
    HomeServer,
    KermiApiError,
    KermiConnectionError,
    KermiInvalidAuth,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import KermiClient
    from .data import KermiXCenterConfigEntry


@dataclass(slots=True)
class KermiXCenterSnapshot:
    """Everything one poll cycle collected from the portal."""

    home_servers: dict[str, HomeServer] = field(default_factory=dict)
    devices: dict[str, list[Device]] = field(default_factory=dict)


class KermiXCenterDataUpdateCoordinator(DataUpdateCoordinator[KermiXCenterSnapshot]):
    """Coordinate polling of the Kermi X-Center portal."""

    config_entry: KermiXCenterConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: KermiXCenterConfigEntry,
        client: KermiClient,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self._client = client

    async def _async_update_data(self) -> KermiXCenterSnapshot:
        try:
            snapshot = KermiXCenterSnapshot()
            for home_server in await self._client.async_get_home_servers():
                snapshot.home_servers[home_server.id] = home_server
                snapshot.devices[home_server.id] = await self._client.async_get_devices(
                    home_server.id
                )
        except KermiInvalidAuth as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (KermiConnectionError, KermiApiError) as err:
            raise UpdateFailed(str(err)) from err
        return snapshot
