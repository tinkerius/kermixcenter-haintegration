"""Config flow for the kermixcenter integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KermiAuth, KermiConnectionError, KermiError, KermiInvalidAuth
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Mapping

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL),
        ),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
        ),
    },
)


class KermiXCenterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config and reauth flow for Kermi X-Center."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow started by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate(user_input)
            if not errors:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],  # noqa: ARG002
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication after the portal rejected the token."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Prompt for a new password during re-authentication."""
        assert self._reauth_entry is not None  # noqa: S101
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._reauth_entry.data, **user_input}
            errors = await self._async_validate(data)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data=data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        ),
                    ),
                },
            ),
            description_placeholders={
                CONF_USERNAME: self._reauth_entry.data[CONF_USERNAME]
            },
            errors=errors,
        )

    async def _async_validate(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Try to log in; return a mapping of form errors (empty on success)."""
        auth = KermiAuth(
            session=async_get_clientsession(self.hass),
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
        )
        try:
            await auth.async_verify_credentials()
        except KermiInvalidAuth:
            return {"base": "invalid_auth"}
        except KermiConnectionError:
            return {"base": "cannot_connect"}
        except KermiError as err:
            LOGGER.exception("Unexpected error verifying Kermi credentials: %s", err)
            return {"base": "unknown"}
        return {}
