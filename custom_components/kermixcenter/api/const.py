"""Constants for the Kermi X-Center portal API."""

from __future__ import annotations

from typing import Final

# Public web portal that the browser UI talks to.
PORTAL_BASE_URL: Final = "https://portal.kermi.com"

# OpenIddict identity server embedded in the portal.
OPENID_AUTHORITY: Final = f"{PORTAL_BASE_URL}/openid"
OPENID_CONFIGURATION_URL: Final = f"{OPENID_AUTHORITY}/.well-known/openid-configuration"
AUTHORIZE_ENDPOINT: Final = f"{OPENID_AUTHORITY}/connect/authorize"
TOKEN_ENDPOINT: Final = f"{OPENID_AUTHORITY}/connect/token"

# OAuth2 public client used by the X-Center single page app (no client secret).
CLIENT_ID: Final = "XCenterUI"
REDIRECT_URI: Final = f"{PORTAL_BASE_URL}/xcenterui/xcenter/auth/loginCallback"
SCOPE: Final = "openid email profile offline_access kermi.xcenter kermi.webcrm"

# REST API that serves device and datapoint data.
API_BASE_URL: Final = f"{PORTAL_BASE_URL}/xcenterpro/api"

# Refresh the access token this many seconds before it actually expires.
TOKEN_EXPIRY_LEEWAY: Final = 60

DEFAULT_TIMEOUT: Final = 30

# BMS device type identifiers seen on the portal.
DEVICE_TYPE_CONTROLLER: Final = 0
DEVICE_TYPE_HEAT_PUMP: Final = 2
DEVICE_TYPE_VENTILATION: Final = 40

# DatapointConfig.DatapointType values.
DATAPOINT_TYPE_ENUM: Final = 0  # integer; enumerated when PossibleValues is set
DATAPOINT_TYPE_NUMBER: Final = 1  # float measurement
DATAPOINT_TYPE_BOOL: Final = 2
DATAPOINT_TYPE_STRING: Final = 3

# A normal end user has UserLevel 10; higher levels are installer/service.
USER_LEVEL_END_USER: Final = 10

# Placeholder GUID the portal uses for "no id".
ZERO_GUID: Final = "00000000-0000-0000-0000-000000000000"
