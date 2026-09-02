"""Config flow for Ecowitt Public Station.

Each config entry = one station (one MAC or IMEI). This keeps HA's device
registry clean (one HA "device" per weather station) and lets you add as
many public/shared stations as you like by repeating Settings > Devices &
Services > Add Integration > Ecowitt Public Station.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    EcowittAuthError,
    EcowittClient,
    EcowittCredentials,
    EcowittDeviceError,
    EcowittRateLimitError,
)
from .const import (
    CONF_API_KEY,
    CONF_APPLICATION_KEY,
    CONF_IMEI,
    CONF_MAC,
    CONF_SCAN_INTERVAL,
    CONF_STATION_NAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


def _base_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_APPLICATION_KEY, default=defaults.get(CONF_APPLICATION_KEY, "")
            ): str,
            vol.Required(CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")): str,
            vol.Optional(CONF_MAC, default=defaults.get(CONF_MAC, "")): str,
            vol.Optional(CONF_IMEI, default=defaults.get(CONF_IMEI, "")): str,
            vol.Optional(
                CONF_STATION_NAME, default=defaults.get(CONF_STATION_NAME, "")
            ): str,
        }
    )


class EcowittPublicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a single Ecowitt station."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input.get(CONF_MAC, "").strip()
            imei = user_input.get(CONF_IMEI, "").strip()

            if not mac and not imei:
                errors["base"] = "mac_or_imei_required"
            else:
                session = async_get_clientsession(self.hass)
                client = EcowittClient(
                    session,
                    EcowittCredentials(
                        application_key=user_input[CONF_APPLICATION_KEY].strip(),
                        api_key=user_input[CONF_API_KEY].strip(),
                    ),
                )
                try:
                    info = await client.get_device_info(
                        mac=mac or None, imei=imei or None
                    )
                except EcowittAuthError:
                    errors["base"] = "invalid_auth"
                except EcowittDeviceError:
                    errors["base"] = "invalid_device"
                except EcowittRateLimitError:
                    errors["base"] = "rate_limited"
                except aiohttp.ClientError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error validating Ecowitt station")
                    errors["base"] = "unknown"

                if not errors:
                    unique_id = mac or imei
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    station_name = (
                        user_input.get(CONF_STATION_NAME, "").strip()
                        or info.get("name")
                        or f"Ecowitt {unique_id}"
                    )

                    data = {
                        CONF_APPLICATION_KEY: user_input[CONF_APPLICATION_KEY].strip(),
                        CONF_API_KEY: user_input[CONF_API_KEY].strip(),
                        CONF_MAC: mac or None,
                        CONF_IMEI: imei or None,
                        CONF_STATION_NAME: station_name,
                    }
                    return self.async_create_entry(title=station_name, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_base_schema(user_input),
            errors=errors,
            description_placeholders={
                "docs_url": "https://doc.ecowitt.net/web/#/apiv3en"
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EcowittPublicOptionsFlow:
        return EcowittPublicOptionsFlow(config_entry)


class EcowittPublicOptionsFlow(config_entries.OptionsFlow):
    """Let the user change polling interval after setup without re-adding."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MINUTES)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
