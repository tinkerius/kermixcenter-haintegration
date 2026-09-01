"""Constants for the kermixcenter integration."""

from __future__ import annotations

from datetime import timedelta
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "kermixcenter"
ATTRIBUTION = "Data provided by the Kermi X-Center portal"

MANUFACTURER = "Kermi"
MODEL = "X-Center"

# The portal is a cloud service; poll conservatively.
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

# homeassistant.helpers.storage.Store version for the discovered datapoint cache.
STORAGE_VERSION = 1

CONF_HOME_SERVER_ID = "home_server_id"
