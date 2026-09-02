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
    DATAPOINT_TYPE_STRING,
    USER_LEVEL_END_USER,
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
    """Metadata describing a single datapoint of a device type.

    ``DatapointConfigId`` is a catalogue key namespaced by device type: it is the
    same for every installation that has that device type.
    """

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
    possible_values: dict[str, str]
    menu_entry_id: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_bool(self) -> bool:
        """Whether this datapoint carries a boolean flag."""
        return self.datapoint_type == DATAPOINT_TYPE_BOOL

    @property
    def is_string(self) -> bool:
        """Whether this datapoint carries free text."""
        return self.datapoint_type == DATAPOINT_TYPE_STRING

    @property
    def is_enumerated(self) -> bool:
        """Whether this datapoint has a fixed set of named integer states."""
        return bool(self.possible_values) and not self.is_bool

    @property
    def is_numeric(self) -> bool:
        """Whether this datapoint is a plain number (no enum labels)."""
        return (
            self.datapoint_type in (DATAPOINT_TYPE_ENUM, DATAPOINT_TYPE_NUMBER)
            and not self.is_enumerated
        )

    @property
    def is_writable(self) -> bool:
        """Whether a normal end user may write this datapoint."""
        return self.user_level_write <= USER_LEVEL_END_USER

    @property
    def clr_type(self) -> str:
        """The .NET value type, for building a WriteValues ``$type``."""
        return {
            DATAPOINT_TYPE_NUMBER: "System.Single",
            DATAPOINT_TYPE_BOOL: "System.Boolean",
            DATAPOINT_TYPE_STRING: "System.String",
        }.get(self.datapoint_type, "System.Int32")

    @property
    def write_type_string(self) -> str:
        """Full polymorphic ``$type`` string for a WriteValues item."""
        return (
            f"BMS.Shared.DatapointCore.DatapointValue`1"
            f"[[{self.clr_type}, mscorlib]], BMS.Shared"
        )

    def label_for(self, value: Any) -> str | None:
        """Return the display label for an enumerated value, if known."""
        return self.possible_values.get(str(value))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatapointConfig:
        """Build a :class:`DatapointConfig` from a portal datapoint ``Config``."""
        raw_possible = data.get("PossibleValues")
        possible: dict[str, str] = {}
        if isinstance(raw_possible, dict):
            # Some (badly translated) datapoints return empty labels - fall back
            # to the raw key so the option is still usable.
            possible = {str(k): (str(v) or str(k)) for k, v in raw_possible.items()}
        elif isinstance(raw_possible, list):
            for item in raw_possible:
                if isinstance(item, dict) and "Value" in item:
                    possible[str(item["Value"])] = str(
                        item.get("DisplayName") or item.get("Key") or item["Value"]
                    )
        return cls(
            id=data["DatapointConfigId"],
            well_known_name=data.get("WellKnownName") or None,
            display_name=data.get("DisplayName") or "",
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
class MenuDatapoint:
    """A datapoint config together with where it sits in the device menu."""

    config: DatapointConfig
    menu_path: tuple[str, ...]


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
    "DatapointConfig",
    "DatapointValue",
    "Device",
    "HomeServer",
    "MenuDatapoint",
]
