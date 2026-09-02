"""Sensor platform for Ecowitt Public Station.

Because different stations expose wildly different sensor sets (a basic
console might only report outdoor temp/humidity, while a full array reports
soil moisture, PM2.5, lightning, multiple temp/humidity channels, battery
levels, etc.), entities are created dynamically from whatever the first
real_time payload actually contains, rather than a fixed hardcoded list.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_IMEI, CONF_MAC, CONF_STATION_NAME, DOMAIN
from .coordinator import EcowittStationCoordinator

_LOGGER = logging.getLogger(__name__)

# Best-effort mapping from Ecowitt unit strings to HA device classes / state
# classes. Anything not listed here still gets created as a plain numeric or
# text sensor using whatever unit string Ecowitt returns.
_UNIT_DEVICE_CLASS: dict[str, SensorDeviceClass] = {
    "°f": SensorDeviceClass.TEMPERATURE,
    "°c": SensorDeviceClass.TEMPERATURE,
    "%": SensorDeviceClass.HUMIDITY,
    "inhg": SensorDeviceClass.PRESSURE,
    "hpa": SensorDeviceClass.PRESSURE,
    "mmhg": SensorDeviceClass.PRESSURE,
    "w/m2": SensorDeviceClass.IRRADIANCE,
    "μg/m3": SensorDeviceClass.PM25,
    "mph": SensorDeviceClass.WIND_SPEED,
    "km/h": SensorDeviceClass.WIND_SPEED,
    "m/s": SensorDeviceClass.WIND_SPEED,
    "in": None,
    "mm": None,
}

_MEASUREMENT_CATEGORIES = {
    "temperature",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_gust",
    "solar",
    "uv",
    "pm25",
    "pm10",
    "co2",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: EcowittStationCoordinator = data["coordinator"]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.data.get(CONF_MAC) or entry.data.get(CONF_IMEI))},
        name=entry.data[CONF_STATION_NAME],
        manufacturer="Ecowitt",
        model="Public/Shared Weather Station",
    )

    entities: list[EcowittSensor] = []
    for field_key in coordinator.data or {}:
        entities.append(EcowittSensor(coordinator, entry, field_key, device_info))

    async_add_entities(entities)

    # Ecowitt stations occasionally add sensors later (e.g. a new soil probe
    # is paired). Watch for keys we haven't created entities for yet and add
    # them on the fly rather than requiring a reload.
    known_keys = {e.field_key for e in entities}

    def _add_new_entities() -> None:
        new_keys = set(coordinator.data or {}) - known_keys
        if not new_keys:
            return
        new_entities = [
            EcowittSensor(coordinator, entry, key, device_info) for key in new_keys
        ]
        known_keys.update(new_keys)
        async_add_entities(new_entities)

    coordinator.async_add_listener(_add_new_entities)


class EcowittSensor(CoordinatorEntity[EcowittStationCoordinator], SensorEntity):
    """One sensor entity per Ecowitt field (e.g. outdoor_temperature)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EcowittStationCoordinator,
        entry: ConfigEntry,
        field_key: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self.field_key = field_key
        self._attr_unique_id = f"{entry.entry_id}_{field_key}"
        self._attr_translation_key = None
        self._attr_name = field_key.replace("_", " ").title()
        self._attr_device_info = device_info

        sample = coordinator.data.get(field_key, {}) if coordinator.data else {}
        unit = str(sample.get("unit", "")).strip()
        self._attr_native_unit_of_measurement = unit or None

        unit_lower = unit.lower()
        device_class = _UNIT_DEVICE_CLASS.get(unit_lower)
        if device_class is not None:
            self._attr_device_class = device_class

        if any(cat in field_key for cat in _MEASUREMENT_CATEGORIES):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif "rain" in field_key and (
            "rate" not in field_key
        ):
            # cumulative rain counters
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif "rain" in field_key and "rate" in field_key:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        field = self.coordinator.data.get(self.field_key)
        if not field:
            return None
        value = field.get("value")
        try:
            return float(value)
        except (TypeError, ValueError):
            return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        field = (self.coordinator.data or {}).get(self.field_key, {})
        attrs = {}
        if "time" in field:
            attrs["observed_at"] = field["time"]
        return attrs
