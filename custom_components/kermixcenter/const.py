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
