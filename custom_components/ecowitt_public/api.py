"""Thin async client for the Ecowitt v3 public API.

Docs: https://doc.ecowitt.net/web/#/apiv3en

Notes on scope:
    Ecowitt's v3 API is device-centric. There is no endpoint to search for
    "public stations near me" the way Weather Underground's PWS map works.
    To pull a station's data you must already know its MAC (Wi-Fi gateways)
    or IMEI (cellular gateways), and that station's data must either be your
    own, or have been explicitly shared with your Ecowitt account by its
    owner (Ecowitt calls this "device sharing" in the ecowitt.net web UI /
    app). This client does not fabricate a discovery feature that the
    upstream API doesn't provide.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp
import async_timeout

from .const import (
    DEVICE_INFO_ENDPOINT,
    ERROR_CODES,
    HISTORY_ENDPOINT,
    REAL_TIME_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20


class EcowittApiError(Exception):
    """Base error for anything the API itself reports as a failure."""

    def __init__(self, code: str | int | None, message: str) -> None:
        self.code = str(code) if code is not None else None
        self.message = message
        friendly = ERROR_CODES.get(self.code, message)
        super().__init__(f"Ecowitt API error {self.code}: {friendly}")


class EcowittAuthError(EcowittApiError):
    """Raised for bad application_key / api_key."""


class EcowittDeviceError(EcowittApiError):
    """Raised for a bad/unshared MAC or IMEI."""


class EcowittRateLimitError(EcowittApiError):
    """Raised when the daily call quota is exhausted."""


@dataclass
class EcowittCredentials:
    application_key: str
    api_key: str


class EcowittClient:
    """Minimal wrapper around the three endpoints this integration needs."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        credentials: EcowittCredentials,
    ) -> None:
        self._session = session
        self._creds = credentials

    async def _request(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        query = {
            "application_key": self._creds.application_key,
            "api_key": self._creds.api_key,
            **params,
        }
        _LOGGER.debug("GET %s params(minus keys)=%s", url, {
            k: v for k, v in params.items()
        })
        try:
            async with async_timeout.timeout(REQUEST_TIMEOUT):
                async with self._session.get(url, params=query) as resp:
                    resp.raise_for_status()
                    payload = await resp.json(content_type=None)
        except aiohttp.ClientResponseError as err:
            raise EcowittApiError(err.status, str(err)) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise EcowittApiError(None, f"Network error: {err}") from err

        code = str(payload.get("code"))
        if code != "0":
            msg = payload.get("msg", "unknown error")
            if code in ("40010", "40011"):
                raise EcowittAuthError(code, msg)
            if code in ("40012", "43001"):
                raise EcowittDeviceError(code, msg)
            if code == "44001":
                raise EcowittRateLimitError(code, msg)
            raise EcowittApiError(code, msg)

        return payload.get("data", {})

    async def get_device_info(
        self, *, mac: str | None = None, imei: str | None = None
    ) -> dict[str, Any]:
        """Fetch static device info (name, location, etc.) — used to validate a
        station during config flow and to seed device_info in HA."""
        params: dict[str, Any] = {}
        if mac:
            params["mac"] = mac
        if imei:
            params["imei"] = imei
        return await self._request(DEVICE_INFO_ENDPOINT, params)

    async def get_real_time(
        self,
        *,
        mac: str | None = None,
        imei: str | None = None,
        unit_params: dict[str, int] | None = None,
        call_back: str = "all",
    ) -> dict[str, Any]:
        """Fetch current conditions for one station."""
        params: dict[str, Any] = {"call_back": call_back}
        if mac:
            params["mac"] = mac
        if imei:
            params["imei"] = imei
        if unit_params:
            params.update(unit_params)
        return await self._request(REAL_TIME_ENDPOINT, params)

    async def get_history(
        self,
        *,
        mac: str | None = None,
        imei: str | None = None,
        start_date: datetime,
        end_date: datetime,
        cycle_type: str = "auto",
        unit_params: dict[str, int] | None = None,
        call_back: str = "all",
    ) -> dict[str, Any]:
        """Fetch historical data for one station across a date range.

        cycle_type: "auto" | "5min" | "30min" | "240min" | "1day"
        Ecowitt enforces: 5min granularity only within the last ~90 days,
        30min within the last year. Requesting a range that's too old at too
        fine a granularity will come back as a 40013/40014 error from their
        side; we don't pre-block it, we just surface their error clearly.
        """
        params: dict[str, Any] = {
            "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
            "cycle_type": cycle_type,
            "call_back": call_back,
        }
        if mac:
            params["mac"] = mac
        if imei:
            params["imei"] = imei
        if unit_params:
            params.update(unit_params)
        return await self._request(HISTORY_ENDPOINT, params)
