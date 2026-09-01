"""Classification of Kermi datapoints into Home Assistant entities.

Discovery (the menu walk) returns *every* datapoint a device exposes - ~200 for
a heat pump. Creating 200 enabled entities would be unusable, so:

* every non-hidden datapoint becomes an entity (nothing is lost),
* only datapoints in :data:`CURATED` are enabled by default; the rest are created
  disabled and the user turns on what they want,
* datapoints without a ``WellKnownName`` are always created disabled.

``CURATED`` and :data:`HINTS` are keyed by ``WellKnownName``, which is stable
across installations, so this table is portable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)

from .api.models import DatapointConfig

if TYPE_CHECKING:
    from .api import MenuDatapoint

PLATFORM_SENSOR = "sensor"
PLATFORM_BINARY_SENSOR = "binary_sensor"


@dataclass(slots=True)
class DiscoveredDatapoint:
    """A datapoint bound to the device instance it was discovered on."""

    home_server_id: str
    home_server_name: str
    device_id: str
    device_serial: str
    device_name: str
    device_type: int
    device_sw_version: str
    menu_path: tuple[str, ...]
    config: DatapointConfig

    @property
    def device_key(self) -> str:
        """Stable per-device key (serial when the portal provides one)."""
        return self.device_serial or self.device_id

    @property
    def device_identifier(self) -> str:
        """Value for the HA device registry identifier."""
        return f"{self.home_server_id}_{self.device_key}"

    @property
    def unique_id(self) -> str:
        """Globally unique entity id.

        ``home_server_id`` keeps two houses apart, ``device_key`` keeps two
        devices of the same type apart, ``config.id`` is the datapoint.
        """
        return f"{self.home_server_id}_{self.device_key}_{self.config.id}"

    @property
    def platform(self) -> str:
        """Which HA platform should own this datapoint."""
        return PLATFORM_BINARY_SENSOR if self.config.is_bool else PLATFORM_SENSOR

    @property
    def suggested_name(self) -> str:
        """Entity name (device name is prepended by HA via has_entity_name)."""
        name = self.config.display_name.strip() or self.config.well_known_name or "?"
        if self.config.well_known_name in CURATED or not self.menu_path:
            return name
        # Disambiguate the long tail with the deepest menu section.
        return f"{self.menu_path[-1]} {name}".strip()

    @property
    def enabled_default(self) -> bool:
        """Whether the entity is enabled the first time it is created."""
        wkn = self.config.well_known_name
        if not wkn:
            return False
        return wkn in CURATED

    def to_storage(self) -> dict[str, Any]:
        """Serialise for :class:`homeassistant.helpers.storage.Store`."""
        return {
            "home_server_id": self.home_server_id,
            "home_server_name": self.home_server_name,
            "device_id": self.device_id,
            "device_serial": self.device_serial,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "device_sw_version": self.device_sw_version,
            "menu_path": list(self.menu_path),
            "config": self.config.raw,
        }

    @classmethod
    def from_storage(cls, data: dict[str, Any]) -> DiscoveredDatapoint:
        """Rebuild from :meth:`to_storage` output."""
        return cls(
            home_server_id=data["home_server_id"],
            home_server_name=data["home_server_name"],
            device_id=data["device_id"],
            device_serial=data.get("device_serial", ""),
            device_name=data["device_name"],
            device_type=int(data.get("device_type", -1)),
            device_sw_version=data.get("device_sw_version", ""),
            menu_path=tuple(data.get("menu_path", [])),
            config=DatapointConfig.from_dict(data["config"]),
        )

    @classmethod
    def build(
        cls,
        *,
        home_server_id: str,
        home_server_name: str,
        device: Any,
        menu_datapoint: MenuDatapoint,
    ) -> DiscoveredDatapoint:
        """Bind a discovered :class:`MenuDatapoint` to its device."""
        return cls(
            home_server_id=home_server_id,
            home_server_name=home_server_name,
            device_id=device.id,
            device_serial=device.serial
            if device.serial and "0000" not in device.serial
            else "",
            device_name=device.name,
            device_type=device.device_type,
            device_sw_version=device.software_version,
            menu_path=menu_datapoint.menu_path,
            config=menu_datapoint.config,
        )


@dataclass(frozen=True)
class DatapointHint:
    """Presentation overrides for a datapoint, keyed by WellKnownName."""

    device_class: str | None = None
    state_class: str | None = None
    unit: str | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None


# Portal unit string -> (HA device class, HA state class, HA unit).
_UNIT_MAP: dict[str, tuple[str | None, str | None, str | None]] = {
    "°C": (
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        UnitOfTemperature.CELSIUS,
    ),
    "K": (None, SensorStateClass.MEASUREMENT, UnitOfTemperature.KELVIN),
    "%": (None, SensorStateClass.MEASUREMENT, PERCENTAGE),
    "kW": (
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
        UnitOfPower.KILO_WATT,
    ),
    "W": (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, UnitOfPower.WATT),
    "kWh": (
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
        UnitOfEnergy.KILO_WATT_HOUR,
    ),
    "Wh": (
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
        UnitOfEnergy.WATT_HOUR,
    ),
    "l/min": (
        SensorDeviceClass.VOLUME_FLOW_RATE,
        SensorStateClass.MEASUREMENT,
        UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
    ),
    "bar": (
        SensorDeviceClass.PRESSURE,
        SensorStateClass.MEASUREMENT,
        UnitOfPressure.BAR,
    ),
    "rpm": (None, SensorStateClass.MEASUREMENT, REVOLUTIONS_PER_MINUTE),
    "h": (SensorDeviceClass.DURATION, None, UnitOfTime.HOURS),
    "min": (SensorDeviceClass.DURATION, None, UnitOfTime.MINUTES),
    "s": (SensorDeviceClass.DURATION, None, UnitOfTime.SECONDS),
    "Tage": (SensorDeviceClass.DURATION, None, UnitOfTime.DAYS),
    "V": (SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "V"),
    "A": (SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, "A"),
}

_ENERGY = DatapointHint(
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    unit=UnitOfEnergy.KILO_WATT_HOUR,
)
_COP = DatapointHint(state_class=SensorStateClass.MEASUREMENT, icon="mdi:heat-pump")
_RUNTIME = DatapointHint(
    device_class=SensorDeviceClass.DURATION,
    state_class=SensorStateClass.TOTAL_INCREASING,
    entity_category=EntityCategory.DIAGNOSTIC,
)

HINTS: dict[str, DatapointHint] = {
    "HP_WaermemengeGesamt": _ENERGY,
    "HP_WaermemengeHeizung": _ENERGY,
    "HP_WaermemengeTWE": _ENERGY,
    "HP_StrommengeGesamt": _ENERGY,
    "HP_HeatingWaterElectricalEnergy": _ENERGY,
    "HP_HotWaterElectricalEnergy": _ENERGY,
    "HP_TotalCOP": _COP,
    "HP_SCOPGesamt": _COP,
    "HP_HeatingWaterAverageCOP": _COP,
    "HP_HotWaterAverageCOP": _COP,
    "HP_BetriebsstundenGesamt": _RUNTIME,
    "HP_HeatingWaterOperatingMinutes": _RUNTIME,
    "HP_HotWaterOperatingMinutes": _RUNTIME,
    "HP_HeatpumpState": DatapointHint(icon="mdi:heat-pump"),
    "KWL_Lüftungsstufe": DatapointHint(icon="mdi:fan"),
}

# WellKnownNames whose entities are enabled by default.
CURATED: frozenset[str] = frozenset(
    {
        # heat pump - temperatures
        "Aussentemperatur_gemittelt",
        "LuftTemperatur",
        "HP_AuslasstempLadekreis",
        "HP_EinlasstempLadekreis",
        "HP_EinlasstempGeokreis",
        "HP_AuslasstempGeokreis",
        "HP_IstTempHW",
        "HP_HeizwasserSollwertPanel",
        "HP_TWETempIst",
        "HP_TWESoll",
        "HP_MK1IstTemp",
        "HP_MK1SollTempPanel",
        # heat pump - operation
        "HP_HeatpumpState",
        "HP_OperationState",
        "HP_SmartGridStatus",
        "HPxyz_DurchflussIstLadekreis",
        "HP_HeatOutput",
        "HP_AktuelleMotorleistungKW",
        "HP_General_TWE",
        # heat pump - efficiency / energy
        "HP_TotalCOP",
        "HP_SCOPGesamt",
        "HP_HeatingWaterAverageCOP",
        "HP_HotWaterAverageCOP",
        "HP_WaermemengeGesamt",
        "HP_WaermemengeHeizung",
        "HP_WaermemengeTWE",
        "HP_StrommengeGesamt",
        "HP_BetriebsstundenGesamt",
        # ventilation
        "KWL_Lüftungsstufe",
        "SchaltzustandEinAus",
        "KWL_ZulufttemperaturT2",
        "KWL_AblufttemperaturT3",
        "KWL_FortlufttemperaturT4",
        "KWL_Auslastung_Ventilator_1",
        "KWL_Auslastung_Ventilator_2",
        "KWL_Party_Modus",
        "KWL_Urlaubs_Modus",
        "KWL_Sommer_Bypassklappe_Aktiv",
    }
)


@dataclass(slots=True)
class SensorPresentation:
    """Resolved presentation for a sensor entity."""

    device_class: str | None = None
    state_class: str | None = None
    unit: str | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None
    options: list[str] | None = field(default=None)


def resolve_sensor(config: DatapointConfig) -> SensorPresentation:
    """Work out device_class / state_class / unit for a sensor datapoint."""
    hint = HINTS.get(config.well_known_name or "", DatapointHint())

    if config.is_enumerated:
        return SensorPresentation(
            device_class=SensorDeviceClass.ENUM,
            options=sorted(set(config.possible_values.values())),
            icon=hint.icon,
            entity_category=hint.entity_category,
        )
    if config.is_string:
        return SensorPresentation(
            icon=hint.icon,
            entity_category=hint.entity_category or EntityCategory.DIAGNOSTIC,
        )

    unit_dc, unit_sc, ha_unit = _UNIT_MAP.get(config.unit, (None, None, None))
    return SensorPresentation(
        device_class=hint.device_class or unit_dc,
        state_class=hint.state_class or unit_sc or SensorStateClass.MEASUREMENT,
        unit=hint.unit or ha_unit or (config.unit or None),
        entity_category=hint.entity_category,
        icon=hint.icon,
    )


def resolve_binary_sensor(config: DatapointConfig) -> BinarySensorDeviceClass | None:
    """Pick a binary_sensor device class (mostly there isn't a good one)."""
    wkn = (config.well_known_name or "").lower()
    if "alarm" in wkn or "stoerung" in wkn or "störung" in wkn:
        return BinarySensorDeviceClass.PROBLEM
    return None
