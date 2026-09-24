---
name: add-datapoint
description: Enable, tune or make writable a Kermi datapoint (curate CURATED / HINTS / WRITABLE in datapoints.py). Use when a user wants a sensor enabled by default, a better unit/device_class/icon, or a datapoint exposed as a number/select/switch control.
---

# Curate a Kermi datapoint

All classification lives in `custom_components/kermixcenter/datapoints.py` and is keyed by
**`WellKnownName`**, which is identical across every installation of the same device type.
Datapoints without a `WellKnownName` cannot be curated (they stay disabled by default).

## 1. Find the datapoint

Get its `WellKnownName`, `DatapointType`, `Unit`, `PossibleValues`, `UserLevelWrite`:

- In HA: the entity's attributes (`extra_state_attributes` in `entity.py`) show the
  well-known name and config id, or
- `python3 scripts/kermi_probe.py --dump out.json` (needs `.env` credentials) and search the
  dump. Never commit the dump — it contains installation IDs.

## 2. Pick the table

| Goal | Edit |
| --- | --- |
| Enabled by default | add the name to `CURATED` |
| device_class / state_class / unit / icon / entity_category override | add a `DatapointHint` to `HINTS` (reuse `_ENERGY`, `_COP`, `_RUNTIME` where they fit); generic unit mapping is in `_UNIT_MAP` |
| Writable control | add `"<WellKnownName>": PLATFORM_NUMBER / PLATFORM_SELECT / PLATFORM_SWITCH` to `WRITABLE` |

`WRITABLE` rules (see `DiscoveredDatapoint.platform`): the platform must match the datapoint
type — `switch` needs a bool, `select` an enum (`PossibleValues`), `number` a numeric type —
otherwise it silently falls back to sensor. Do **not** rely on `UserLevelWrite` alone: the
portal marks read-only status values as writable. Only add genuine user settings.

Energy counters (kWh, cumulative) → `SensorDeviceClass.ENERGY` + `TOTAL_INCREASING` so they
work in the Energy dashboard.

## 3. Consequences to mention in the PR

- The `unique_id` does not change, so history is kept.
- Moving a datapoint into `WRITABLE` changes its platform: the old `sensor`/`binary_sensor`
  entity becomes orphaned and users must delete it once. Note this in the PR description.
- `CURATED` only affects **newly created** entities; existing disabled entities stay disabled.

## 4. Verify

1. `scripts/lint`.
2. `scripts/develop`, reload the integration, check the entity appears with the expected
   platform, unit and enabled state.
3. For controls: test with a **no-op write** (set the current value again) before changing
   anything real on the heat pump.
