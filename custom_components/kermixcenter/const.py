"""Constants for the kermixcenter integration."""

from __future__ import annotations

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "kermixcenter"
ATTRIBUTION = "Data provided by the Kermi X-Center portal"

MANUFACTURER = "Kermi"
MODEL = "X-Center"

# Poll interval (seconds). The portal is a cloud service, so poll conservatively.
# Overridable via the options flow.
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 3600

# homeassistant.helpers.storage.Store version for the discovered datapoint cache
# and the cached OAuth token.
STORAGE_VERSION = 1

CONF_HOME_SERVER_ID = "home_server_id"

CONF_LANGUAGE = "language"
DEFAULT_LANGUAGE = "de"
# Languages the portal actually translates the datapoint catalogue into.
# key = option value / HA-language match, value = the Accept-Language header sent.
SUPPORTED_LANGUAGES: dict[str, str] = {
    "de": "de",
    "fr": "fr-FR",
    "nl": "nl-NL",
    "cs": "cs-CZ",
}


def resolve_language(configured: str | None, ha_language: str | None) -> str:
    """Pick a supported catalogue language.

    Prefer an explicit option, else the Home Assistant UI language, else German.
    """
    if configured in SUPPORTED_LANGUAGES:
        return configured  # type: ignore[return-value]
    short = (ha_language or "").split("-")[0].lower()
    return short if short in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
