# Kermi X-Center for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) custom integration for
**Kermi X-Center** heating and ventilation systems (x-change heat pumps, x-well
ventilation, …), talking to the **Kermi cloud portal** at
`portal.kermi.com`.

Kermi X-Center has **no local API** — the portal is the only way in. This
integration reproduces what the portal web app does: it signs in with your
portal account, discovers every datapoint your installation exposes, and turns
them into Home Assistant entities.

> **Status:** functional. Authentication, discovery and sensors are tested
> against a live installation. A **curated set of controls** (write) is
> supported — DHW setpoint, MK1 heating settings, ventilation modes/level, …
> — the rest stays read-only.
>
> This is an **unofficial** project and not affiliated with or endorsed by
> Kermi. It relies on an undocumented API that may change or break at any time.
> **Writing changes real settings on your heating system** — use with care.

## Requirements

- Home Assistant **2026.6** or newer
- A **Kermi X-Center portal account** (the email address and password you use at
  <https://portal.kermi.com/XCenterUI/>)
- No multi-factor authentication on the account (only username + password is
  supported)
- Your X-Center home server must be **online** and connected to the portal

## Installation

### HACS

1. HACS → three-dot menu → **Custom repositories**.
2. Add `https://github.com/tinkerius/kermixcenter-haintegration`,
   category **Integration**.
3. Install **Kermi X-Center** and restart Home Assistant.

### Manual

Download `kermixcenter.zip` from the
[latest release](https://github.com/tinkerius/kermixcenter-haintegration/releases/latest),
unpack it into `config/custom_components/kermixcenter/` and restart Home Assistant.

## Setup

**Settings → Devices & Services → Add Integration → Kermi X-Center**, then enter
your portal email and password.

On first setup the integration walks your installation's menu tree and discovers
every datapoint (typically 200+ for a heat pump). It creates an entity for each
one, but only enables a **curated default set** (~40: flow/return/buffer/DHW
temperatures, operating state, COP, energy totals, power, fan level, …). The
rest are created **disabled** — enable the ones you want in the entity settings.

### Options

**Settings → Devices & Services → Kermi X-Center → Configure**

| Option | Default | Notes |
| --- | --- | --- |
| **Polling interval** | 60 s | 30–3600 s. Values are only as fresh as your home server's last push to the portal. |
| **Datapoint language** | your HA language, else German | The portal only translates names into **German, French, Dutch and Czech**. Anything else falls back to German — there is no English. Changing this re-scans and renames entities on the next reload. |

## Devices & entities

- One Home Assistant **device per Kermi device** — an X-Center "hub" with the
  heat pump, ventilation unit, etc. linked under it.
- Entity names come from the datapoint's portal name (and its menu section, for
  the non-curated ones).
- `entity_id`s and history are stable across restarts, re-discovery and language
  changes — they key off device/datapoint IDs, not names.
- **Energy dashboard:** the `kWh` totals (heat quantity, electrical energy) are
  exposed as `total_increasing` sensors and can be added under
  **Settings → Dashboards → Energy**.

### Controls (write)

A hand-picked set of datapoints is exposed as writable entities (the portal
marks many read-only status values as "writable", so this is a curated list,
not everything with write permission):

| Type | Examples |
| --- | --- |
| `number` | DHW target & one-time target, MK1 constant setpoint, heating-curve parallel shift, eco/normal/comfort offsets, summer/winter changeover temps |
| `select` | MK1 operating mode & season, heating-mode selection, energy mode, ventilation level |
| `switch` | DHW enable, one-time DHW charge, quiet mode, ventilation manual/party/holiday, ventilation on/off |

A writable datapoint becomes a `number`/`select`/`switch` instead of a
`sensor`/`binary_sensor` — on an existing install the old read-only entity for
it is left behind and can be deleted.

### Scenes

X-Center **scenes** ("Szenen") are the controller's own rule-based automations —
heating/DHW/ventilation schedules, presence/absence modes, PV / Power-to-Heat
logic. They are exposed on the hub device, disabled by default:

- **`switch` per scene** — enable/disable the scene (e.g. turn on a
  "Power-to-Heat" scene while your PV is exporting)
- **`binary_sensor` per scene** — whether the scene's actions are currently
  applied

New scenes need an integration reload to appear.

### Rediscovering datapoints

If you add hardware later, re-scan without re-adding the integration:

- press the **Rediscover datapoints** button on the X-Center hub device, or
- call the **`kermixcenter.rediscover`** service (optionally targeting one
  installation) from an automation.

Re-discovery is **additive only** — it never renames, disables or removes
existing entities, so your customisations are safe. Devices removed from the
portal simply go *unavailable*.

## How it works

| Step | |
| --- | --- |
| Auth | OAuth2 authorization-code + PKCE against the portal's OpenIddict server; access token cached and refreshed, so restarts don't re-login |
| Discovery | recursive walk of `Menu/GetChildEntries`, cached to storage |
| Polling | one `Datapoint/ReadValues` call per installation per interval |
| Writing | `Datapoint/WriteValues` with the read object, `Value` swapped |

The reverse-engineered API is documented in [`docs/api.md`](docs/api.md).

## Limitations

- **Cloud only** — needs internet, the portal, and an online home server.
- Writing is limited to the curated control set above.
- **Polling** — not real-time; bounded by the portal's own update cadence.
- **Unofficial API** — no stability guarantees.

## Troubleshooting

- **"Re-authentication required":** your password changed or the token was
  revoked — follow the prompt to re-enter it.
- **Enable debug logging:**

  ```yaml
  logger:
    logs:
      custom_components.kermixcenter: debug
  ```

## Development

The repo ships a devcontainer with a standalone Home Assistant instance.

- `scripts/develop` — start Home Assistant with this integration loaded
- `scripts/lint` — run `ruff` (format + check)
- `scripts/kermi_probe.py` — standalone script that logs in and dumps devices /
  datapoints / values (reads credentials from an untracked `.env`; see
  `.env.example`)

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
