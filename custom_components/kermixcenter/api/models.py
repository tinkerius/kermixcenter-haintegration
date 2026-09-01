"""Typed views over the portal's JSON payloads.

The portal wraps everything in ``{"ResponseData": ..., "StatusCode": 0}`` and
uses .NET style PascalCase keys. These dataclasses expose only the fields the
integration needs; the raw dict is kept around for anything not modelled yet.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any

from .const import (
    DATAPOINT_TYPE_BOOL,
    DATAPOINT_TYPE_ENUM,
    DATAPOINT_TYPE_NUMBER,
)


@dataclass(slots=True)
class HomeServer:
    """A physical X-Center installation ("home server") on the account."""

    id: str
    serial: str
    name: str
    version: str
    is_online: bool
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HomeServer:
        """Build a :class:`HomeServer` from a ``GetHomeServers`` entry."""
        return cls(
            id=data["HomeServerId"],
            serial=data.get("Serial", ""),
            name=data.get("DisplayName") or data.get("Serial") or data["HomeServerId"],
            version=data.get("Version", ""),
            is_online=bool(data.get("IsOnline", False)),
            raw=data,
        )


@dataclass(slots=True)
class Device:
    """A device attached to a home server (heat pump, ventilation unit, ...)."""

    id: str
    name: str
    device_type: int
    software_version: str
    serial: str
    is_offline: bool
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Device:
        """Build a :class:`Device` from a ``GetAllDevices`` entry."""
        return cls(
            id=data["DeviceId"],
            name=data.get("Name", ""),
            device_type=int(data.get("DeviceType", -1)),
            software_version=data.get("SoftwareVersion", ""),
            serial=data.get("Serial", ""),
            is_offline=bool(data.get("IsOffline", False)),
            raw=data,
        )


@dataclass(slots=True)
class DatapointConfig:
    """Metadata describing a single datapoint of a device type/version."""

    id: str
    well_known_name: str | None
    display_name: str
    description: str
    unit: str
    datapoint_type: int
    user_level_read: int
    user_level_write: int
    hidden: bool
    min_value: float | None
    max_value: float | None
    scale: float
    offset: float
    possible_values: dict[int, str]
    menu_entry_id: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_number(self) -> bool:
        """Whether this datapoint carries a numeric measurement."""
        return self.datapoint_type == DATAPOINT_TYPE_NUMBER

    @property
    def is_bool(self) -> bool:
        """Whether this datapoint carries a boolean flag."""
        return self.datapoint_type == DATAPOINT_TYPE_BOOL

    @property
    def is_enum(self) -> bool:
        """Whether this datapoint carries an enumerated/integer state."""
        return self.datapoint_type == DATAPOINT_TYPE_ENUM

    @property
    def is_writable(self) -> bool:
        """Whether a normal end user (level 10) may write this datapoint."""
        return self.user_level_write <= 10  # noqa: PLR2004 - portal's user level

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatapointConfig:
        """Build a :class:`DatapointConfig` from a ``GetConfigs`` entry."""
        possible: dict[int, str] = {}
        for item in data.get("PossibleValues") or []:
            if isinstance(item, dict) and "Value" in item:
                possible[int(item["Value"])] = str(
                    item.get("DisplayName") or item.get("Key") or item["Value"]
                )
        return cls(
            id=data["DatapointConfigId"],
            well_known_name=data.get("WellKnownName"),
            display_name=data.get("DisplayName", ""),
            description=data.get("Description") or "",
            unit=data.get("Unit") or "",
            datapoint_type=int(data.get("DatapointType", -1)),
            user_level_read=int(data.get("UserLevelRead", 0)),
            user_level_write=int(data.get("UserLevelWrite", 999)),
            hidden=bool(data.get("Hidden", False)),
            min_value=_maybe_float(data.get("MinValue")),
            max_value=_maybe_float(data.get("MaxValue")),
            scale=float(data.get("Scale") or 1.0),
            offset=float(data.get("Offset") or 0.0),
            possible_values=possible,
            menu_entry_id=data.get("MenuEntryId"),
            raw=data,
        )


@dataclass(slots=True)
class DatapointValue:
    """A current value for a ``(device, datapoint)`` pair."""

    device_id: str
    config_id: str
    value: Any
    clr_type: str
    flags: int
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatapointValue:
        """Build a :class:`DatapointValue` from a ``ReadValues`` entry."""
        return cls(
            device_id=data.get("DeviceId", ""),
            config_id=data.get("DatapointConfigId", ""),
            value=data.get("Value"),
            clr_type=_clr_type(data.get("$type", "")),
            flags=int(data.get("Flags", 0)),
            raw=data,
        )


def _clr_type(type_string: str) -> str:
    """Pull the inner CLR type name out of a ``$type`` annotation."""
    # e.g. "BMS.Shared.DatapointCore.DatapointValue`1[[System.Single, mscorlib]], ..."
    if "[[" in type_string:
        return type_string.split("[[", 1)[1].split(",", 1)[0].strip()
    return type_string


def _maybe_float(value: Any) -> float | None:
    with contextlib.suppress(TypeError, ValueError):
        return float(value)
    return None


__all__ = [
    "DATAPOINT_TYPE_BOOL",
    "DATAPOINT_TYPE_ENUM",
    "DATAPOINT_TYPE_NUMBER",
    "DatapointConfig",
    "DatapointValue",
    "Device",
    "HomeServer",
]
