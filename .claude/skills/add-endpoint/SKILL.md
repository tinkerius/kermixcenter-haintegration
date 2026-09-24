---
name: add-endpoint
description: Add support for a new (reverse-engineered) Kermi X-Center portal API endpoint to the in-repo client. Use when a feature needs portal data or actions the client doesn't cover yet.
---

# Add a portal API endpoint

The portal API is undocumented. Everything known is in `docs/api.md` — read it first; the
endpoint may already be listed under "Known endpoints", "Scenes" or "Also present".

## 1. Find the call

- Browser devtools on <https://portal.kermi.com/XCenterUI/> while doing the action → note
  method, path, body, response. Save HARs outside the repo (`*.har` is gitignored, but
  HARs contain your password/tokens — never share them).
- Or search the portal's bundled SPA JS (autorest-generated client): endpoint names look like
  `api.<Controller>.<Action>(...)`, with a `{destinationId}` path param = home server id.
- Base: `https://portal.kermi.com/xcenterpro/api`, `Authorization: Bearer <token>`, JSON bodies.
  Responses are wrapped in `{ResponseData, StatusCode, DisplayText, DetailedText, ...}`;
  `StatusCode 0` = OK.

## 2. Implement

- `custom_components/kermixcenter/api/client.py`: add an `async_<verb>_<thing>` method
  modelled on its neighbours. Always go through `self._request(...)`, which handles auth,
  token refresh, timeouts and unwraps the envelope into `ResponseData` / raises `KermiApiError`.
  The `api/` package must not import Home Assistant.
- `api/models.py`: add a `from_dict` dataclass if the payload is used beyond a single field.
  Be defensive: fields can be `null`, empty strings or missing.
- Coordinator / platforms: consume it via `coordinator.py`; map errors
  (`KermiInvalidAuth` → `ConfigEntryAuthFailed`, other `KermiError` → `UpdateFailed` /
  `HomeAssistantError`).

## 3. Verify

- Prefer read-only calls first. For state-changing calls, verify with a no-op (e.g. write
  back the current value, disable an already-disabled scene).
- Quick check without HA: extend or copy `scripts/kermi_probe.py` (uses `.env` creds).
- `scripts/lint`.

## 4. Document

Add the endpoint (method, path, body, response shape, what was verified live) to
`docs/api.md`. Mark anything unverified as such. Do not paste real IDs from your installation —
use placeholders like `{hs}` / `<device-id>`.
