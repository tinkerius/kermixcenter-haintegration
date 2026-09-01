"""Custom types for the kermixcenter integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import KermiAuth, KermiClient
    from .coordinator import KermiXCenterDataUpdateCoordinator


type KermiXCenterConfigEntry = ConfigEntry[KermiXCenterData]


@dataclass
class KermiXCenterData:
    """Runtime data stored on the config entry."""

    client: KermiClient
    auth: KermiAuth
    coordinator: KermiXCenterDataUpdateCoordinator
    integration: Integration
