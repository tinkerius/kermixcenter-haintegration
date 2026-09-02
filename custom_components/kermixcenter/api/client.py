"""HTTP client for the Kermi X-Center portal REST API.

Every endpoint lives under ``/xcenterpro/api`` and answers with the envelope
``{"ResponseData": <payload>, "StatusCode": 0, "DisplayText": "", ...}``. A
non-zero ``StatusCode`` is turned into :class:`KermiApiError`.

Authentication is a bearer access token obtained from :class:`KermiAuth`; no
cookies are involved.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import API_BASE_URL, DEFAULT_TIMEOUT, ZERO_GUID
from .exceptions import KermiApiError, KermiConnectionError, KermiInvalidAuth
from .models import (
    DatapointConfig,
    DatapointValue,
    Device,
    HomeServer,
    MenuDatapoint,
    Scene,
)

if TYPE_CHECKING:
    from .auth import KermiAuth

_ZERO_GUID = ZERO_GUID


class KermiClient:
    """Thin async wrapper around the portal API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth: KermiAuth,
        *,
        accept_language: str | None = None,
    ) -> None:
        """Store the shared session and the authentication helper.

        ``accept_language`` (e.g. ``"fr-FR"``) is sent on every request; the
        portal localises datapoint / enum / menu names accordingly. German is the
        fallback when a language is missing.
        """
        self._session = session
        self._auth = auth
        self._accept_language = accept_language

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        _retried: bool = False,
    ) -> Any:
        token = await self._auth.async_get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/plain, */*",
        }
        if self._accept_language:
            headers["Accept-Language"] = self._accept_language
        url = f"{API_BASE_URL}{path}"
        try:
            async with self._session.request(
                method,
                url,
                json=json,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as resp:
                auth_failed = resp.status in (
                    HTTPStatus.UNAUTHORIZED,
                    HTTPStatus.FORBIDDEN,
                )
                if auth_failed and not _retried:
                    # Token might have been revoked server-side; force a fresh
                    # login once before giving up.
                    await self._auth.async_invalidate()
                    return await self._request(method, path, json=json, _retried=True)
                if auth_failed:
                    msg = f"Portal rejected the access token (HTTP {resp.status})"
                    raise KermiInvalidAuth(msg)
                if resp.status >= HTTPStatus.BAD_REQUEST:
                    text = await resp.text()
                    msg = f"HTTP {resp.status} for {path}: {text[:200]}"
                    raise KermiApiError(msg, status_code=resp.status)
                payload = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            msg = f"Request to {path} failed: {err}"
            raise KermiConnectionError(msg) from err

        return self._unwrap(payload, path)

    @staticmethod
    def _unwrap(payload: Any, path: str) -> Any:
        if not isinstance(payload, dict):
            raise KermiApiError(f"Unexpected response for {path}: {payload!r}")
        status = payload.get("StatusCode", 0)
        if status not in (0, None):
            message = (
                payload.get("DetailedText")
                or payload.get("DisplayText")
                or f"StatusCode {status}"
            )
            raise KermiApiError(message, status_code=status)
        return payload.get("ResponseData")

    # -- account / system -------------------------------------------------

    async def async_login_current_user(self) -> dict[str, Any]:
        """Register the current session with the portal; returns permissions."""
        return await self._request("POST", "/WebUser/LoginCurrentUser")

    async def async_get_home_servers(self, *, max_count: int = 20) -> list[HomeServer]:
        """List the X-Center installations visible to the account."""
        data = await self._request(
            "POST",
            "/System/GetHomeServers/",
            json={"Filter": {"MaxCount": max_count}},
        )
        return [HomeServer.from_dict(item) for item in data or []]

    async def async_get_home_server(self, home_server_id: str) -> HomeServer:
        """Return a single home server by id."""
        data = await self._request("GET", f"/System/GetHomeServerById/{home_server_id}")
        return HomeServer.from_dict(data)

    # -- devices --------------------------------------------------------

    async def async_get_devices(self, home_server_id: str) -> list[Device]:
        """List every device on a home server."""
        data = await self._request("GET", f"/Device/GetAllDevices/{home_server_id}")
        return [Device.from_dict(item) for item in data or []]

    async def async_get_devices_by_type(
        self, home_server_id: str, device_type: int, *, with_details: bool = False
    ) -> list[Device]:
        """List devices of a single ``DeviceType``."""
        data = await self._request(
            "POST",
            f"/Device/GetDevicesByType/{home_server_id}",
            json={"DeviceType": device_type, "WithDetails": with_details},
        )
        return [Device.from_dict(item) for item in data or []]

    # -- datapoints ----------------------------------------------------

    async def async_get_datapoint_configs(
        self,
        home_server_id: str,
        *,
        device_type: int,
        device_version: str,
        config_ids: list[str] | None = None,
    ) -> list[DatapointConfig]:
        """Return datapoint metadata for a device type/version.

        ``config_ids`` mirrors what the web UI sends. Whether an empty list makes
        the portal return *all* datapoints is still being verified; the probe
        script checks this.
        """
        body: dict[str, Any] = {
            "DeviceType": device_type,
            "DeviceVersion": device_version,
            "DatapointConfigIds": config_ids or [],
        }
        data = await self._request(
            "POST", f"/Datapoint/GetConfigs/{home_server_id}", json=body
        )
        return [DatapointConfig.from_dict(item) for item in data or []]

    async def async_read_values(
        self,
        home_server_id: str,
        pairs: list[tuple[str, str]],
        *,
        ignore_errors: bool = True,
    ) -> list[DatapointValue]:
        """Read current values for ``(device_id, datapoint_config_id)`` pairs."""
        body = {
            "DatapointValues": [
                {"DeviceId": device_id, "DatapointConfigId": config_id}
                for device_id, config_id in pairs
            ],
            "IgnoreErrors": ignore_errors,
        }
        data = await self._request(
            "POST", f"/Datapoint/ReadValues/{home_server_id}", json=body
        )
        return [DatapointValue.from_dict(item) for item in data or []]

    async def async_write_values(
        self, home_server_id: str, items: list[dict[str, Any]]
    ) -> Any:
        """Write datapoint values.

        Each item must be a full datapoint-value object -- ``$type``,
        ``DatapointConfigId``, ``DeviceId``, ``Flags`` and the new ``Value`` --
        i.e. what ``ReadValues`` returned with ``Value`` swapped. ``Value`` is in
        display units (46.0, not 460).
        """
        return await self._request(
            "POST",
            f"/Datapoint/WriteValues/{home_server_id}",
            json={"DatapointValues": items},
        )

    # -- menu / enums ------------------------------------------------

    async def async_get_menu_child_entries(
        self,
        home_server_id: str,
        device_id: str,
        *,
        parent_menu_entry_id: str = _ZERO_GUID,
        with_details: bool = True,
    ) -> dict[str, Any]:
        """Return the menu tree for a device (entries carry datapoint ids)."""
        return await self._request(
            "POST",
            f"/Menu/GetChildEntries/{home_server_id}",
            json={
                "DeviceId": device_id,
                "ParentMenuEntryId": parent_menu_entry_id,
                "WithDetails": with_details,
            },
        )

    async def async_discover_datapoints(
        self, home_server_id: str, device_id: str
    ) -> list[MenuDatapoint]:
        """Walk a device's whole menu tree and return its unique datapoints.

        ``Datapoint/GetConfigs`` has no "list all" mode, so datapoints are found
        by recursing through ``Menu/GetChildEntries`` and collecting the
        ``Bundles[].Datapoints[].Config`` blocks. This makes one request per menu
        node (dozens per device) so it belongs in setup / occasional refresh, not
        the poll loop. The first menu location a datapoint appears in wins.
        """
        seen: dict[str, MenuDatapoint] = {}

        async def _walk(parent_id: str, path: tuple[str, ...]) -> None:
            res = await self.async_get_menu_child_entries(
                home_server_id, device_id, parent_menu_entry_id=parent_id
            )
            if not isinstance(res, dict):
                return
            for bundle in res.get("Bundles") or []:
                for datapoint in bundle.get("Datapoints") or []:
                    config = datapoint.get("Config")
                    if not isinstance(config, dict):
                        continue
                    config_id = config.get("DatapointConfigId")
                    if config_id and config_id not in seen:
                        seen[config_id] = MenuDatapoint(
                            config=DatapointConfig.from_dict(config), menu_path=path
                        )
            for entry in res.get("MenuEntries") or []:
                entry_id = entry.get("MenuEntryId")
                if entry_id and entry_id != _ZERO_GUID:
                    await _walk(entry_id, (*path, entry.get("DisplayName") or ""))

        await _walk(_ZERO_GUID, ())
        return list(seen.values())

    async def async_resolve_enums(
        self, home_server_id: str, enum_names: list[str], *, filter_profile: int = 1
    ) -> dict[str, dict[int, str]]:
        """Resolve BMS enum names to ``{value: label}`` maps."""
        body = {
            "FilterConfigurations": [
                {"EnumName": name, "FilterProfile": filter_profile}
                for name in enum_names
            ]
        }
        data = await self._request(
            "POST", f"/System/ResolveEnums/{home_server_id}", json=body
        )
        result: dict[str, dict[int, str]] = {}
        for entry in data or []:
            name = entry.get("FilterConfiguration", {}).get("EnumName")
            if not name:
                continue
            result[name] = {
                int(key): meta.get("DisplayName") or meta.get("EnumValueKey") or key
                for key, meta in (entry.get("Metadata") or {}).items()
            }
        return result

    async def async_get_current_alarms(
        self, home_server_id: str, device_id: str
    ) -> list[dict[str, Any]]:
        """Return active alarms for a device."""
        return await self._request(
            "POST",
            f"/Alarm/GetCurrentAlarms/{home_server_id}",
            json={"DeviceId": device_id},
        )

    # -- scenes (rule-based automations) ---------------------------

    async def async_get_scenes(self, home_server_id: str) -> list[Scene]:
        """List the installation's scenes with their current state."""
        data = await self._request("GET", f"/Scene/GetScenesOverview/{home_server_id}")
        return [Scene.from_dict(item) for item in data or []]

    async def async_set_scene_enabled(
        self, home_server_id: str, scene_id: str, *, enabled: bool
    ) -> None:
        """Enable or disable a scene."""
        await self._request(
            "POST",
            f"/Scene/UpdateSceneSettings/{home_server_id}",
            json={"Settings": [{"SceneId": scene_id, "Enabled": enabled}]},
        )

    async def async_execute_scene(self, home_server_id: str, scene_id: str) -> None:
        """Force a scene's actions to run now, ignoring its condition."""
        await self._request(
            "POST",
            f"/Scene/ExecuteScene/{home_server_id}",
            json={"SceneId": scene_id},
        )
