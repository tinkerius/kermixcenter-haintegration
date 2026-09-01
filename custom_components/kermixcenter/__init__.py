"""
Custom integration to integrate Kermi X-Center with Home Assistant.

For more details about this integration, please refer to
https://github.com/tinkerius/kermixcenter-haintegration
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import KermiAuth, KermiClient
from .coordinator import KermiXCenterDataUpdateCoordinator
from .data import KermiXCenterData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import KermiXCenterConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KermiXCenterConfigEntry,
) -> bool:
    """Set up this integration using the UI."""
    session = async_get_clientsession(hass)
    auth = KermiAuth(
        session=session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    client = KermiClient(session, auth)
    coordinator = KermiXCenterDataUpdateCoordinator(hass, entry, client)

    entry.runtime_data = KermiXCenterData(
        client=client,
        auth=auth,
        coordinator=coordinator,
        integration=async_get_loaded_integration(hass, entry.domain),
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: KermiXCenterConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant,
    entry: KermiXCenterConfigEntry,
) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
