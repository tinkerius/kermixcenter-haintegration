# Kermi X-Center for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) custom integration for the **Kermi X-Center** heating/ventilation unit, installable via [HACS](https://hacs.xyz/).

> **Status: work in progress.** This integration was bootstrapped from the
> [`integration_blueprint`](https://github.com/ludeeus/integration_blueprint) template and is not yet
> functional against a real Kermi X-Center device — the API client still talks to a placeholder test
> endpoint and the entities expose placeholder data. See [CONTRIBUTING.md](CONTRIBUTING.md) if you'd
> like to help finish it.

## Installation

### HACS (recommended, once published)

1. In HACS, go to **Integrations** → the `⋮` menu → **Custom repositories**.
2. Add `https://github.com/tinkerius/kermixcenter-haintegration` as an *Integration*.
3. Search for **Kermi X-Center** and install it.
4. Restart Home Assistant.

### Manual

1. Copy the `custom_components/kermixcenter` folder into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.

## Configuration

Configuration is done entirely through the Home Assistant UI:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Kermi X-Center**.
3. Enter your username and password when prompted.

## Entities

The integration currently sets up (placeholder implementations, to be replaced with real Kermi X-Center data points):

| Platform | Description |
| -- | -- |
| Sensor | Example status sensor |
| Binary sensor | Example connectivity sensor |
| Switch | Example toggle |

## Development

This repo includes a devcontainer with a standalone Home Assistant instance for local testing.

1. Open the repo in the VS Code devcontainer.
2. Run `scripts/develop` to start Home Assistant with this integration loaded.
3. Run `scripts/lint` before submitting changes.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

[MIT](LICENSE)
