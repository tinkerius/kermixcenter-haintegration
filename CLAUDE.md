# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository.

## What this is

A Home Assistant **custom integration** (`custom_components/kermixcenter`, domain
`kermixcenter`) for the **Kermi X-Center cloud portal** (<https://portal.kermi.com/XCenterUI/>).
It exposes Kermi heat pumps (x-change dynamic) and ventilation units (x-well) as HA
entities, plus writable controls and the controller's "scenes".

Hard constraints:

- **Cloud only.** Kermi has no local/LAN API; everything goes through the portal.
- **The portal API is undocumented.** It was reverse-engineered from browser traffic and
  the portal's SPA JavaScript. [docs/api.md](docs/api.md) is the reference — read it before
  touching `api/`, and update it whenever you learn something new about the portal.
- **HACS-only** distribution (not aiming for HA core).
- **The API client stays in-repo** under `custom_components/kermixcenter/api/` — no separate
  PyPI library. It must stay free of Home Assistant imports (pure `aiohttp`) so
  `scripts/kermi_probe.py` can use it standalone.

## Commands

| Task | Command |
| --- | --- |
| Install dev dependencies | `scripts/setup` |
| Run Home Assistant with the integration (port 8123, `config/` dir) | `scripts/develop` |
| Format + lint (auto-fix) | `scripts/lint` |
| What CI checks | `ruff check .` and `ruff format . --check` (+ hassfest, HACS) |
| Probe the live portal without HA | `python3 scripts/kermi_probe.py [--dump out.json]` |

`scripts/develop` sets `PYTHONPATH` to include `custom_components/`. The probe reads
`KERMI_USERNAME` / `KERMI_PASSWORD` from the environment or an untracked `.env`
(see `.env.example`). Python 3.14, pinned `homeassistant` in `requirements_dev.txt`.
Ruff runs with `select = ["ALL"]` (see `.ruff.toml`) — docstrings and type hints are expected.

## Architecture

```
custom_components/kermixcenter/
  api/                 # pure aiohttp client, no HA imports
    auth.py            # OAuth2 auth-code + PKCE against the portal's OpenIddict server; refresh
    client.py          # KermiClient: REST calls; _request/_unwrap handle the response envelope
    models.py          # HomeServer, Device, DatapointConfig, DatapointValue, Scene, MenuDatapoint
    const.py           # URLs, client id, device/datapoint type constants
    exceptions.py      # KermiError > KermiConnectionError / KermiAuthError(KermiInvalidAuth) / KermiApiError
  __init__.py          # entry setup: token Store, KermiAuth(on_token_update=...), coordinator, platforms
  config_flow.py       # user + reauth steps; options flow (poll interval, catalogue language)
  coordinator.py       # discovery (menu walk, cached in a Store), polling ReadValues, writes, scenes
  datapoints.py        # classification: CURATED, HINTS, WRITABLE; DiscoveredDatapoint -> platform
  entity.py            # base entities (home server / datapoint / scene) + dynamic entity adding
  sensor.py binary_sensor.py number.py select.py switch.py button.py
  services.py          # kermixcenter.rediscover
  strings.json, translations/en.json
```

Data flow: login → `System/GetHomeServers` + devices → **recursive `Menu/GetChildEntries`
walk** per device yields every datapoint with its embedded config → cached in
`storage.Store` → one `Datapoint/ReadValues` per home server each poll (chunked at 100) →
entities read from the coordinator. New datapoints found on rediscovery are announced via
the `signal_new_datapoints` dispatcher signal.

## Invariants — do not break these

- **Entity `unique_id` = `{home_server_id}_{device_serial_or_id}_{datapoint_config_id}`**
  (`DiscoveredDatapoint.unique_id`). Changing it orphans every user's entities and history.
  It is deliberately independent of display names/language.
- **`DatapointConfigId` and `WellKnownName` are global per `DeviceType`** — identical across
  all installations. That is why `CURATED`, `HINTS` and `WRITABLE` are keyed by
  `WellKnownName`: they are portable. About half the datapoints have no `WellKnownName`;
  those are always created disabled.
- **Discovery is additive.** Rediscovery (button/service) never modifies or removes known
  datapoints, so user customisations survive.
- **Every non-hidden datapoint becomes an entity**; only `CURATED` ones are enabled by default
  (a heat pump exposes ~200 datapoints).
- **Values are already scaled.** `ReadValues` returns display units (43.3 °C) and writes send
  display units. Never apply `Scale`/`Offset`.
- **Writes** (`Datapoint/WriteValues`) send the exact object `ReadValues` returned with
  `Value` replaced. The `$type` discriminator (`System.Single` / `Int32` / `Boolean` /
  `String`) is required — the coordinator keeps raw `DatapointValue` objects for this.
- **`UserLevelWrite <= 10` is not a reliable "writable" signal** — the portal marks read-only
  status values (even `HP_HeatpumpState`) as writable. Only the curated `WRITABLE` allowlist
  in `datapoints.py` turns a datapoint into a `number`/`select`/`switch`.
- **Localisation** comes from the `Accept-Language` header. The portal supports only
  `de` (base), `fr`, `nl-NL`, `cs-CZ` — there is **no English**. A language change triggers
  a fresh discovery (the Store records the language).
- **Login page has two `<form class="login-form">`** (password + Microsoft Entra). The parser
  picks the one with a password input; don't "simplify" that away.
- Access tokens are opaque encrypted JWEs (3600 s); never try to decode them.

## Conventions

- Match the surrounding code style (dataclasses with `slots=True`, `from __future__ import
  annotations`, docstrings on everything, `LOGGER` from `const.py`).
- Change `strings.json` **and** `translations/en.json` together.
- hassfest rejects URLs inside strings — pass them via `description_placeholders`.
- New portal endpoint → method in `api/client.py` (via `_request`), model in `api/models.py`,
  row in `docs/api.md`.
- Map `KermiInvalidAuth` → `ConfigEntryAuthFailed`, other `KermiError` →
  `ConfigEntryNotReady` / `UpdateFailed` / `HomeAssistantError` as the context requires.

## Testing and verification

There is **no automated test suite yet** (contributions welcome — `pytest-homeassistant-
custom-component` is the natural choice). Today, verification means:

1. `scripts/lint` is clean.
2. `scripts/kermi_probe.py` against a real account for API-level changes.
3. `scripts/develop`, add the integration at <http://localhost:8123>, check the log.

You need your own Kermi portal account. **When verifying writes against a real heat pump,
use no-op writes** (write back the current value) unless you really intend to change the
installation. Never commit `.env`, `config/.storage/`, HAR captures or probe dumps — they
contain credentials, tokens and installation IDs.

## Known gaps / good first issues

- Poll only enabled datapoints (currently all discovered datapoints are read every cycle).
- Add a test suite (config flow, datapoint classification, client envelope handling).
- Installer-contact string datapoints still create (disabled) entities — could be filtered.
- No live push; SignalR/WebSocket channel of the portal is not yet investigated.
- New portal scenes need an integration reload to appear.
- A datapoint moved into `WRITABLE` leaves its old sensor entity orphaned (user must delete).
