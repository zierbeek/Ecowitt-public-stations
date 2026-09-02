"""The Ecowitt Public Station integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EcowittApiError, EcowittClient, EcowittCredentials
from .const import (
    ATTR_CYCLE_TYPE,
    ATTR_END_DATE,
    ATTR_START_DATE,
    ATTR_STATION_MAC,
    CONF_API_KEY,
    CONF_APPLICATION_KEY,
    CONF_IMEI,
    CONF_MAC,
    CONF_SCAN_INTERVAL,
    CONF_STATION_NAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    SERVICE_GET_HISTORY,
)
from .coordinator import DEFAULT_UNIT_PARAMS, EcowittStationCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

GET_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_STATION_MAC): cv.string,
        vol.Required(ATTR_START_DATE): cv.string,
        vol.Required(ATTR_END_DATE): cv.string,
        vol.Optional(ATTR_CYCLE_TYPE, default="auto"): vol.In(
            ["auto", "5min", "30min", "240min", "1day"]
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one Ecowitt station from a config entry."""
    session = async_get_clientsession(hass)
    client = EcowittClient(
        session,
        EcowittCredentials(
            application_key=entry.data[CONF_APPLICATION_KEY],
            api_key=entry.data[CONF_API_KEY],
        ),
    )

    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)

    coordinator = EcowittStationCoordinator(
        hass,
        client,
        mac=entry.data.get(CONF_MAC),
        imei=entry.data.get(CONF_IMEI),
        station_name=entry.data[CONF_STATION_NAME],
        update_interval_minutes=interval,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # noqa: BLE001
        raise ConfigEntryNotReady(
            f"Could not fetch initial data for {entry.data[CONF_STATION_NAME]}: {err}"
        ) from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options (e.g. scan interval) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the get_history service once, regardless of how many stations
    are configured. It looks up which config entry's credentials to use by
    matching the mac/imei you pass in against configured entries."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_HISTORY):
        return

    async def _handle_get_history(call: ServiceCall) -> ServiceResponse:
        target_mac = call.data[ATTR_STATION_MAC]
        start_date = _parse_date(call.data[ATTR_START_DATE])
        end_date = _parse_date(call.data[ATTR_END_DATE])
        cycle_type = call.data.get(ATTR_CYCLE_TYPE, "auto")

        entry_data = None
        matched_entry = None
        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            coordinator: EcowittStationCoordinator = data["coordinator"]
            if target_mac in (coordinator.mac, coordinator.imei):
                entry_data = data
                matched_entry = entry_id
                break

        if entry_data is None:
            raise HomeAssistantError(
                f"No configured Ecowitt station matches MAC/IMEI '{target_mac}'. "
                "Add it first via Settings > Devices & Services."
            )

        client: EcowittClient = entry_data["client"]
        coordinator: EcowittStationCoordinator = entry_data["coordinator"]

        try:
            raw = await client.get_history(
                mac=coordinator.mac,
                imei=coordinator.imei,
                start_date=start_date,
                end_date=end_date,
                cycle_type=cycle_type,
                unit_params=DEFAULT_UNIT_PARAMS,
            )
        except EcowittApiError as err:
            raise HomeAssistantError(str(err)) from err

        return {"station": coordinator.station_name, "mac": target_mac, "data": raw}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_HISTORY,
        _handle_get_history,
        schema=GET_HISTORY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def _parse_date(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise HomeAssistantError(
        f"Could not parse date '{value}'. Use 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'."
    )
