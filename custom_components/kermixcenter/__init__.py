"""
Custom integration to integrate Kermi X-Center with Home Assistant.

For more details about this integration, please refer to
https://github.com/tinkerius/kermixcenter-haintegration
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_loaded_integration

from .api import KermiAuth, KermiClient, KermiToken
from .const import (
    CONF_LANGUAGE,
    DOMAIN,
    STORAGE_VERSION,
    SUPPORTED_LANGUAGES,
    resolve_language,
)
from .coordinator import KermiXCenterDataUpdateCoordinator
from .data import KermiXCenterData
from .services import async_setup_services

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .data import KermiXCenterConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


def _token_store(hass: HomeAssistant, entry_id: str) -> Store[dict]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.token")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: ARG001
    """Register integration-wide services."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KermiXCenterConfigEntry,
) -> bool:
    """Set up this integration using the UI."""
    token_store = _token_store(hass, entry.entry_id)
    stored_token = await token_store.async_load()
    token = KermiToken.from_dict(stored_token) if stored_token else None

    @callback
    def _persist_token(new_token: KermiToken) -> None:
        # Debounced write so an hourly refresh does not hammer storage.
        token_store.async_delay_save(new_token.to_dict, 1)

    language = resolve_language(entry.options.get(CONF_LANGUAGE), hass.config.language)

    session = async_get_clientsession(hass)
    auth = KermiAuth(
        session=session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        token=token,
        on_token_update=_persist_token,
    )
    client = KermiClient(session, auth, accept_language=SUPPORTED_LANGUAGES[language])
    coordinator = KermiXCenterDataUpdateCoordinator(hass, entry, client, language)

    entry.runtime_data = KermiXCenterData(
        client=client,
        auth=auth,
        coordinator=coordinator,
        integration=async_get_loaded_integration(hass, entry.domain),
    )

    await coordinator.async_setup()
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


async def async_remove_entry(
    hass: HomeAssistant, entry: KermiXCenterConfigEntry
) -> None:
    """Clean up stored data when the entry is deleted."""
    await _token_store(hass, entry.entry_id).async_remove()
    await Store(
        hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.datapoints"
    ).async_remove()


async def _async_reload_entry(
    hass: HomeAssistant,
    entry: KermiXCenterConfigEntry,
) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
