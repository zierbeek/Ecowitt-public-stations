"""Constants for the Ecowitt Public Station integration."""
from __future__ import annotations

DOMAIN = "ecowitt_public"

CONF_APPLICATION_KEY = "application_key"
CONF_API_KEY = "api_key"
CONF_MAC = "mac"
CONF_IMEI = "imei"
CONF_STATION_NAME = "station_name"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL_MINUTES = 5
MIN_SCAN_INTERVAL_MINUTES = 1

API_BASE_URL = "https://api.ecowitt.net/api/v3"
REAL_TIME_ENDPOINT = f"{API_BASE_URL}/device/real_time"
HISTORY_ENDPOINT = f"{API_BASE_URL}/device/history"
DEVICE_INFO_ENDPOINT = f"{API_BASE_URL}/device/info"

# Ecowitt's server-side retention limits (informational; enforced by their API,
# not by us, but useful for validating date ranges before we bother calling out).
HISTORY_5MIN_RETENTION_DAYS = 90
HISTORY_30MIN_RETENTION_DAYS = 365

# Unit ids Ecowitt's API accepts (subset most useful for a US/EU mixed audience).
# See: doc.ecowitt.net API v3 docs, "unit" params on real_time / history.
# Not consumed directly yet — coordinator.py hardcodes DEFAULT_UNIT_PARAMS.
# Kept here as the reference table for a future "choose your units" option.
UNIT_PARAMS = {
    "temp_unitid": {"celsius": 1, "fahrenheit": 2},
    "pressure_unitid": {"hpa": 3, "inhg": 4, "mmhg": 5},
    "wind_speed_unitid": {
        "mps": 6,
        "kmh": 7,
        "knots": 8,
        "mph": 9,
        "bft": 10,
        "fpm": 11,
    },
    "rainfall_unitid": {"mm": 12, "in": 13},
    "solar_irradiance_unitid": {"wm2": 14, "kluxlux": 15, "kfcfc": 16},
}

DEFAULT_TEMP_UNITID = 2  # Fahrenheit
DEFAULT_PRESSURE_UNITID = 4  # inHg
DEFAULT_WIND_SPEED_UNITID = 9  # mph
DEFAULT_RAINFALL_UNITID = 13  # in
DEFAULT_SOLAR_UNITID = 14  # W/m^2

ATTR_STATION_MAC = "mac"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"
ATTR_CYCLE_TYPE = "cycle_type"

SERVICE_GET_HISTORY = "get_history"

ERROR_CODES = {
    "-1": "System busy, try again later",
    "40000": "Illegal parameter",
    "40010": "Illegal Application_Key",
    "40011": "Illegal Api_Key",
    "40012": "Illegal MAC/IMEI",
    "40013": "Illegal start or end date",
    "40014": "Illegal cycle type",
    "40015": "Illegal call_back",
    "40016": "Illegal created time of the device",
    "40017": "Parameter error",
    "43001": "No device was found by MAC/IMEI, or it isn't shared/bound to this account",
    "44001": "API key expired or the daily call limit was exceeded",
}
