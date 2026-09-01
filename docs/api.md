# Kermi X-Center portal — reverse-engineered API notes

The Kermi X-Center web portal (<https://portal.kermi.com/XCenterUI/>) has **no
public or documented API**. These notes were reconstructed from browser traffic
(HAR captures) so the integration can talk to it. Everything here may change
without notice if Kermi updates the portal.

There is no local/LAN interface — the portal is the only way in.

## 1. Authentication

The portal SPA authenticates against an **OpenIddict** identity server at
`https://portal.kermi.com/openid` using the OAuth2 **authorization code flow with
PKCE**. The client is **public** (no client secret).

Discovery document: `GET https://portal.kermi.com/openid/.well-known/openid-configuration`

| Parameter | Value |
| --- | --- |
| `client_id` | `XCenterUI` |
| `redirect_uri` | `https://portal.kermi.com/xcenterui/xcenter/auth/loginCallback` |
| `scope` | `openid email profile offline_access kermi.xcenter kermi.webcrm` |
| `response_type` | `code` |
| `code_challenge_method` | `S256` |
| authorize endpoint | `https://portal.kermi.com/openid/connect/authorize` |
| token endpoint | `https://portal.kermi.com/openid/connect/token` |

### Flow

Steps 1–4 need a shared cookie jar; step 5 does not.

1. `GET /openid/connect/authorize?client_id=…&redirect_uri=…&response_type=code&scope=…&state=<rand>&code_challenge=<S256(verifier)>&code_challenge_method=S256`
   → `302` to `/openid/Account/Login?ReturnUrl=<url-encoded authorize path>`.
   Sets an OpenIddict request cookie.
2. `GET /openid/Account/Login?ReturnUrl=…` → `200` HTML. The form contains a
   hidden `__RequestVerificationToken`; the response sets an
   `.AspNetCore.Antiforgery.*` cookie.
3. `POST` the form `action` (`application/x-www-form-urlencoded`):
   `Login=<email>`, `Password=<password>`, `__RequestVerificationToken=<from HTML>`,
   `login=` (empty submit field).
   → `302` back to `/openid/connect/authorize?…` (sets the `.OpenIdAuth` cookie).
   A `200` here instead means the credentials were rejected.

   **Gotcha:** the login page has *two* `<form class="login-form">` — the
   username/password form (`action="/openid?returnurl=…"`) and a "sign in with
   Microsoft Entra" form (`action="/openid/Account/LoginEntra?…"`). Pick the one
   containing an `<input type="password">`, or you end up at
   `login.microsoftonline.com`.
4. `GET /openid/connect/authorize?…` again (cookies attached)
   → `302` to `…/loginCallback?code=<code>&state=<state>&iss=…`.
   Do **not** follow into the SPA — just read `code` from the query.
5. `POST /openid/connect/token` (`application/x-www-form-urlencoded`):
   `grant_type=authorization_code`, `code`, `redirect_uri`, `code_verifier`,
   `client_id=XCenterUI`
   → JSON `{ access_token, token_type: "Bearer", expires_in: 3600,
   refresh_token, id_token, scope }`.

### Refresh

`POST /openid/connect/token` with `grant_type=refresh_token`,
`refresh_token=<rt>`, `client_id=XCenterUI`. `offline_access` in the scope is what
yields the refresh token.

### Notes

- The `access_token` is an **encrypted JWE** (`alg: RSA-OAEP, enc: A256CBC-HS512`).
  It is opaque to clients — do not try to decode claims, just send it back.
- Access-token lifetime is **3600 s**.
- The `id_token` is a normal readable JWT (`sub`, `email`, `username`).
- `GET /openid/connect/userinfo` with the bearer token returns
  `{ sub, username, email, … }`.

Implemented in [`custom_components/kermixcenter/api/auth.py`](../custom_components/kermixcenter/api/auth.py).

## 2. REST API

Base URL: `https://portal.kermi.com/xcenterpro/api`

- Auth: `Authorization: Bearer <access_token>` — **no cookies required**.
- Request bodies: JSON (`Content-Type: application/json`). Some older calls use
  `application/json-patch+json`; plain JSON works.
- Every response is wrapped:

  ```json
  { "ResponseData": <payload>, "StatusCode": 0,
    "ExceptionData": null, "DisplayText": "", "DetailedText": "" }
  ```

  `StatusCode: 0` = OK. Non-zero → treat `DetailedText`/`DisplayText` as the error.

- Most paths end in `/{homeServerId}`. A few use the zero GUID
  `00000000-0000-0000-0000-000000000000` as a placeholder.

### Known endpoints

| Method & path | Body | Returns |
| --- | --- | --- |
| `POST /System/GetHomeServers/` | `{"Filter":{"MaxCount":20}}` | list of installations |
| `GET  /System/GetHomeServerById/{hs}` | – | one installation |
| `POST /WebUser/LoginCurrentUser` | – | `{ Permissions: [...] }` (call once per session) |
| `GET  /Device/GetAllDevices/{hs}` | – | all devices |
| `POST /Device/GetDevicesByType/{hs}` | `{"DeviceType":2,"WithDetails":false}` | devices of one type |
| `POST /Device/GetDevicesByFilter/{hs}` | `{"WithDetails":true,"WithChildDevices":true,"Recursive":true,"DeviceTypes":[],"MenuEntries":[]}` | filtered devices |
| `POST /Datapoint/GetConfigs/{hs}` | `{"DeviceType":2,"DeviceVersion":"6.4","DatapointConfigIds":[…]}` | datapoint metadata |
| `POST /Datapoint/ReadValues/{hs}` | `{"DatapointValues":[{"DeviceId":…,"DatapointConfigId":…}],"IgnoreErrors":true}` | current values |
| `POST /Menu/GetChildEntries/{hs}` | `{"DeviceId":…,"ParentMenuEntryId":"0…0","WithDetails":true}` | menu tree; entries carry `VisualizationDatapoints` |
| `POST /System/ResolveEnums/{hs}` | `{"FilterConfigurations":[{"EnumName":"HeatpumpState","FilterProfile":1}]}` | `{ value: label }` maps |
| `POST /Alarm/GetCurrentAlarms/{hs}` | `{"DeviceId":…}` | active alarms |
| `POST /Favorite/GetFavorites/{hs}` | `{"WithDetails":true,"OnlyHomeScreen":true}` | user's pinned datapoints |

### Data model

**Device** — `DeviceId`, `Name`, `DeviceType`, `SoftwareVersion`, `Serial`,
`DeviceOptions` (feature flags), `ParentDeviceId`.

Device types seen: `0` = X-Center controller, `2` = *x-change dynamic* (air/water
heat pump), `3` = another heat-pump variant, `40` = *x-well* (ventilation).
On the reference system the heating circuits (MK1/MK3) are **datapoints on the
heat-pump device**, not separate devices.

**DatapointConfig** — `DatapointConfigId`, `WellKnownName` (stable semantic key,
e.g. `HP_HeatpumpState`), `DisplayName` (localised), `Description`, `Unit`,
`DatapointType` (`0` enum/int, `1` number, `2` bool), `UserLevelRead`,
`UserLevelWrite` (10 = normal user, 20/30/40 = installer/service — used to decide
what is writable), `MinValue`, `MaxValue`, `Scale`, `Offset`, `PossibleValues`,
`MenuEntryId`, `Hidden`.

**DatapointValue** — `$type` (CLR type: `System.Single` / `System.Int32` /
`System.Boolean` / `System.DateTime`), `Value` (already decoded and scaled — a
temperature comes back as `43.3`, do **not** re-apply `Scale`),
`DatapointConfigId`, `DeviceId`, `Flags` (bitmask; exact meaning TBD, values
`0/2/5/13/18/26` observed).

### Datapoint discovery (verified live)

`Datapoint/GetConfigs` with an empty `DatapointConfigIds` returns `[]` — there is
no bulk listing that way. Instead, **walk the menu tree**:

1. `POST /Menu/GetChildEntries/{hs}` with `{"DeviceId": <dev>, "ParentMenuEntryId":
   "00000000-0000-0000-0000-000000000000", "WithDetails": true}`.
2. The response has `MenuEntries[]` *and* `Bundles[]`.
   - Recurse into each `MenuEntries[].MenuEntryId`.
   - Collect every `Bundles[].Datapoints[]` — each has a full embedded `Config`
     (`DatapointConfigId`, `WellKnownName`, `DisplayName`, `Unit`, `Scale`,
     `PossibleValues`, `Colors`, `Category`, `UserLevelRead/Write`,
     `DatapointType`).
3. Deduplicate by `DatapointConfigId`.
4. `POST /Datapoint/ReadValues/{hs}` for live values; poll that on the interval
   and re-walk the menu only occasionally.

On the reference system this yields **193 datapoints for the heat pump** and
**34 for the ventilation unit**. `DatapointType`: `0` int/enum (enum when
`PossibleValues` is set), `1` float, `2` bool, `3` string. Roughly half the
datapoints have a blank `WellKnownName`, so `DatapointConfigId` is the stable key.

`POST /Device/GetDevicesByFilter/{hs}` with `WithDetails/WithChildDevices/
Recursive: true` also returns a small `VisualizationDatapoints[]` per device —
that is just the portal's overview-dashboard tile set.

### Enums

- `HeatpumpState`: `0` Off · `1` Standby · `2` Heating · `3` Hot water ·
  `4` Defrost · `5` EVU lock · `6` Alarm · `7` Cooling · `8` Lock
- `HeatingCircuitState`: `0` Off · `1` Heating · `2` Cooling

### How the integration uses this

* **Discovery** (`coordinator._async_discover`): for each device, `client.async_discover_datapoints`
  walks the menu tree and returns `MenuDatapoint`s. The result is cached with
  `homeassistant.helpers.storage.Store` so entities appear instantly on restart,
  and re-run additively by the per-installation **"Rediscover datapoints"**
  button. Known datapoints are never modified or removed.
* **Entities**: every non-hidden datapoint becomes a `sensor` (numeric / enum /
  text) or `binary_sensor` (bool). Only `WellKnownName`s in
  `datapoints.CURATED` are enabled by default; the rest are created disabled.
  `unique_id` = `{home_server_id}_{device_serial_or_id}_{datapoint_config_id}`.
* **Polling** (`coordinator._async_update_data`): one `Datapoint/ReadValues` per
  home server (chunked at 100 pairs) every 60 s.

### Not yet captured

- Writing a datapoint (a `SetValue` / `WriteValues` endpoint) - needed for the
  planned `number` / `select` entities.
- Any SignalR / WebSocket channel for live push updates.
