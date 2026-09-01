"""DataUpdateCoordinator for the kermixcenter integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KermiApiError, KermiConnectionError, KermiError, KermiInvalidAuth
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, STORAGE_VERSION
from .datapoints import DiscoveredDatapoint

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import Device, HomeServer, KermiClient
    from .data import KermiXCenterConfigEntry

_READ_CHUNK = 100

# Device types worth walking for datapoints (skip the bare controller).
_SKIP_DEVICE_TYPES = frozenset({0})

type ValueMap = dict[tuple[str, str], Any]


class KermiXCenterDataUpdateCoordinator(DataUpdateCoordinator[ValueMap]):
    """Poll datapoint values; hold the discovered datapoint catalogue."""

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
        self._store: Store[list[dict[str, Any]]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{config_entry.entry_id}.datapoints"
        )
        self.home_servers: dict[str, HomeServer] = {}
        self.devices: dict[str, list[Device]] = {}
        self.datapoints: dict[str, DiscoveredDatapoint] = {}

    @property
    def signal_new_datapoints(self) -> str:
        """Dispatcher signal fired when discovery adds datapoints."""
        return f"{DOMAIN}_{self.config_entry.entry_id}_new_datapoints"

    # -- setup / discovery --------------------------------------------

    async def async_setup(self) -> None:
        """Load servers + devices, then the datapoint catalogue."""
        try:
            await self._async_load_topology()
        except KermiInvalidAuth as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KermiError as err:
            raise ConfigEntryNotReady(str(err)) from err

        stored = await self._store.async_load()
        if stored:
            self.datapoints = {
                dp.unique_id: dp
                for dp in (DiscoveredDatapoint.from_storage(item) for item in stored)
            }
            LOGGER.debug("Restored %d datapoints from storage", len(self.datapoints))
        else:
            await self._async_discover()

    async def async_rediscover(self) -> int:
        """Re-scan every device's menu tree for datapoints (button / service).

        Purely additive: known datapoints are left untouched so entity
        customisations survive. Returns the number of datapoints added.
        """
        try:
            await self._async_load_topology()
            return await self._async_discover()
        except KermiError as err:
            raise HomeAssistantError(f"Kermi rediscovery failed: {err}") from err

    async def _async_discover(self) -> int:
        added = 0
        for home_server in self.home_servers.values():
            for device in self.devices.get(home_server.id, []):
                if device.device_type in _SKIP_DEVICE_TYPES:
                    continue
                try:
                    found = await self._client.async_discover_datapoints(
                        home_server.id, device.id
                    )
                except KermiApiError as err:
                    LOGGER.warning(
                        "Datapoint discovery failed for %s: %s", device.name, err
                    )
                    continue
                for menu_datapoint in found:
                    if menu_datapoint.config.hidden:
                        continue
                    discovered = DiscoveredDatapoint.build(
                        home_server_id=home_server.id,
                        home_server_name=home_server.name,
                        device=device,
                        menu_datapoint=menu_datapoint,
                    )
                    if discovered.unique_id not in self.datapoints:
                        self.datapoints[discovered.unique_id] = discovered
                        added += 1

        await self._store.async_save(
            [dp.to_storage() for dp in self.datapoints.values()]
        )
        LOGGER.info(
            "Discovery complete: %d datapoints total (%d new)",
            len(self.datapoints),
            added,
        )
        if added:
            async_dispatcher_send(self.hass, self.signal_new_datapoints)
        return added

    async def _async_load_topology(self) -> None:
        servers = await self._client.async_get_home_servers()
        self.home_servers = {hs.id: hs for hs in servers}
        for hs in servers:
            self.devices[hs.id] = await self._client.async_get_devices(hs.id)

    # -- polling -----------------------------------------------------

    async def _async_update_data(self) -> ValueMap:
        values: ValueMap = {}
        try:
            servers = await self._client.async_get_home_servers()
            self.home_servers = {hs.id: hs for hs in servers}

            by_server: dict[str, list[tuple[str, str]]] = {}
            for dp in self.datapoints.values():
                by_server.setdefault(dp.home_server_id, []).append(
                    (dp.device_id, dp.config.id)
                )
            for home_server_id, pairs in by_server.items():
                for start in range(0, len(pairs), _READ_CHUNK):
                    chunk = pairs[start : start + _READ_CHUNK]
                    for value in await self._client.async_read_values(
                        home_server_id, chunk
                    ):
                        values[value.device_id, value.config_id] = value.value
        except KermiInvalidAuth as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (KermiConnectionError, KermiApiError) as err:
            raise UpdateFailed(str(err)) from err
        return values

    # -- lookups used by entities ----------------------------------

    def value_for(self, datapoint: DiscoveredDatapoint) -> Any:
        """Return the last polled value for a datapoint, or ``None``."""
        return (self.data or {}).get((datapoint.device_id, datapoint.config.id))

    def has_value(self, datapoint: DiscoveredDatapoint) -> bool:
        """Whether the last poll returned a value for this datapoint."""
        return (datapoint.device_id, datapoint.config.id) in (self.data or {})
