"""DataUpdateCoordinator that polls current conditions for one station."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import EcowittApiError, EcowittClient
from .const import (
    DEFAULT_PRESSURE_UNITID,
    DEFAULT_RAINFALL_UNITID,
    DEFAULT_SOLAR_UNITID,
    DEFAULT_TEMP_UNITID,
    DEFAULT_WIND_SPEED_UNITID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_UNIT_PARAMS = {
    "temp_unitid": DEFAULT_TEMP_UNITID,
    "pressure_unitid": DEFAULT_PRESSURE_UNITID,
    "wind_speed_unitid": DEFAULT_WIND_SPEED_UNITID,
    "rainfall_unitid": DEFAULT_RAINFALL_UNITID,
    "solar_irradiance_unitid": DEFAULT_SOLAR_UNITID,
}


def flatten_real_time(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Flatten Ecowitt's nested real_time payload into {key: {value, unit}}.

    Ecowitt nests results by category, e.g.:
        {
          "outdoor": {"temperature": {"time": ..., "unit": "°F", "value": "71.2"}},
          "wind": {"wind_speed": {...}},
          ...
        }
    We flatten to top-level keys like "outdoor_temperature" so each becomes
    one HA sensor entity, while keeping the category prefix for clarity since
    stations vary wildly in which sensors they expose.
    """
    flat: dict[str, dict[str, Any]] = {}
    for category, fields in data.items():
        if not isinstance(fields, dict):
            continue
        for field_name, field_value in fields.items():
            if isinstance(field_value, dict) and "value" in field_value:
                flat[f"{category}_{field_name}"] = field_value
            elif isinstance(field_value, dict):
                # one more level of nesting (e.g. battery categories)
                for sub_name, sub_value in field_value.items():
                    if isinstance(sub_value, dict) and "value" in sub_value:
                        flat[f"{category}_{field_name}_{sub_name}"] = sub_value
    return flat


class EcowittStationCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls device/real_time for a single station on an interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EcowittClient,
        *,
        mac: str | None,
        imei: str | None,
        station_name: str,
        update_interval_minutes: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}:{station_name}",
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        self._client = client
        self.mac = mac
        self.imei = imei
        self.station_name = station_name

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            raw = await self._client.get_real_time(
                mac=self.mac,
                imei=self.imei,
                unit_params=DEFAULT_UNIT_PARAMS,
            )
        except EcowittApiError as err:
            raise UpdateFailed(str(err)) from err

        return flatten_real_time(raw)
