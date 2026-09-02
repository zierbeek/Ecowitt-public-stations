# Ecowitt Public Station (HACS custom integration)

A Home Assistant custom integration that pulls **current** and **historical**
weather data from the [Ecowitt](https://www.ecowitt.net) public v3 API — for
your own station, or any other station whose owner has shared it with your
Ecowitt account.

## Important scope note (read this first)

Ecowitt's v3 API is **device-centric**, not location-based. There is
**no "find public stations near me" endpoint** — that's a feature some other
networks (e.g. Weather Underground's PWS map) have, but Ecowitt's API does
not expose it. To pull a station's data you need to already know its
**MAC address** (Wi-Fi gateways) or **IMEI** (cellular gateways), and one of:

- it's your own station, or
- the owner has explicitly shared it with your Ecowitt account (via the
  Ecowitt app/website's device sharing feature), or
- you otherwise legitimately have the MAC (e.g. a community/club station
  whose operator published it).

This integration is built around that reality: you add stations by MAC/IMEI,
not by searching a map. If Ecowitt adds a discovery endpoint in the future,
this integration would need an update to use it.

## What it does

- **Current conditions**: one HA "device" per station, with a dynamically
  generated sensor entity for every field that station actually reports
  (temperature, humidity, pressure, wind, rain, solar/UV, soil moisture,
  PM2.5, lightning, battery levels, etc. — whatever that station has).
  Polled on a configurable interval (default 5 minutes).
- **Historical data**: a Home Assistant service/action,
  `ecowitt_public.get_history`, that fetches a date range from Ecowitt and
  returns it as service response data — usable in scripts, automations, or
  just from Developer Tools → Actions for testing.

## Installation (HACS, custom repository)

1. HACS → the "⋮" menu (top right) → **Custom repositories**.
2. Add this repo's URL, category **Integration**.
3. Install **Ecowitt Public Station**, then restart Home Assistant.

Or manually: copy `custom_components/ecowitt_public/` into your HA
`config/custom_components/` folder and restart.

## Setup

1. Get an **Application Key** and **API Key** from
   [ecowitt.net](https://www.ecowitt.net) → your profile page (free account,
   no station of your own required to *generate* keys, but you'll need
   station access as described above to pull data).
2. In HA: **Settings → Devices & Services → Add Integration → Ecowitt Public
   Station**.
3. Enter the Application Key, API Key, and the MAC (or IMEI) of the station.
4. Repeat for each additional station — each config entry is one station /
   one HA device.
5. Optional: click **Configure** on the integration entry afterward to
   change the polling interval.

## Testing the historical data service

Developer Tools → Actions → search for **Ecowitt Public Station: Get
historical data**. Example YAML:

```yaml
action: ecowitt_public.get_history
data:
  mac: "AA:BB:CC:DD:EE:FF"
  start_date: "2026-08-01"
  end_date: "2026-08-07"
  cycle_type: auto
```

Tick "Show response data" in the UI (or add `response_variable:` in a
script/automation) to see the returned JSON.

**Retention limits enforced by Ecowitt's servers** (not by this
integration):
- 5-minute resolution: roughly the last 90 days
- 30-minute resolution: roughly the last 1 year
- Requesting fine resolution too far back will come back as an API error,
  which the service call will raise as a Home Assistant error with Ecowitt's
  message attached.

## Units

Defaults to °F, inHg, mph, inches, W/m². This is hardcoded in
`coordinator.py` (`DEFAULT_UNIT_PARAMS`) for now — if you want metric,
either edit that dict or open an issue / PR to expose it as a config option.

## Known limitations / things to sanity-check before relying on this

- Only tested against the documented API shape; Ecowitt's actual JSON
  nesting can vary by station/sensor type, so some fields may come through
  named a little differently than expected. Check
  **Developer Tools → States** after adding a station and file an issue with
  the raw payload if something looks off.
- Rate limits are per Application Key across *all* your stations combined —
  polling many stations on a short interval can burn through your daily
  quota. Widen the polling interval via the options flow if you hit
  `44001` errors in the logs.
- No local/offline mode — this always calls Ecowitt's cloud API
  (`iot_class: cloud_polling`).

## License

MIT
