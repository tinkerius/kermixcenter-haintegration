"""Services for the kermixcenter integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from .data import KermiXCenterConfigEntry

SERVICE_REDISCOVER = "rediscover"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

_REDISCOVER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            {"integration": DOMAIN},
        ),
    },
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services (once, for the lifetime of Home Assistant)."""

    async def _async_rediscover(call: ServiceCall) -> None:
        """Re-scan one or all Kermi installations for new datapoints."""
        entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
        if entry_id is not None:
            entry = hass.config_entries.async_get_entry(entry_id)
            if (
                entry is None
                or entry.domain != DOMAIN
                or entry.state is not ConfigEntryState.LOADED
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entry_not_found",
                )
            entries: list[KermiXCenterConfigEntry] = [entry]  # type: ignore[list-item]
        else:
            entries = list(hass.config_entries.async_loaded_entries(DOMAIN))

        for entry in entries:
            coordinator = entry.runtime_data.coordinator
            added = await coordinator.async_rediscover()
            LOGGER.info(
                "Service rediscover for %s: %d new datapoints", entry.title, added
            )
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_REDISCOVER, _async_rediscover, schema=_REDISCOVER_SCHEMA
    )
