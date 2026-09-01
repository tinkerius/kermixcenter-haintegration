#!/usr/bin/env python3
"""Manual probe for the Kermi X-Center portal API.

Runs the real authentication flow and dumps devices, datapoint configs and a few
live values. Use it to validate the client against the live portal and to
discover which datapoints exist for your installation.

Credentials are read from environment variables or an untracked ``.env`` file in
the repository root::

    KERMI_USERNAME=you@example.com
    KERMI_PASSWORD=secret

Usage::

    python3 scripts/kermi_probe.py                  # summary
    python3 scripts/kermi_probe.py --dump out.json  # full JSON dump
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "custom_components" / "kermixcenter"))

# ruff: noqa: E402  (imports follow the sys.path bootstrap above)
import aiohttp
from api import KermiAuth, KermiClient, KermiError
from api.const import DEVICE_TYPE_HEAT_PUMP, DEVICE_TYPE_VENTILATION

PROBE_DEVICE_TYPES = (DEVICE_TYPE_HEAT_PUMP, DEVICE_TYPE_VENTILATION)


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _mask(token: str) -> str:
    return f"{token[:12]}…{token[-6:]} ({len(token)} chars)" if token else "<none>"


def _json_default(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: v for k, v in dataclasses.asdict(obj).items() if k != "raw"}
    raise TypeError(type(obj))


async def _probe_device(client: KermiClient, hs_id: str, dev: Any) -> dict[str, Any]:
    print(f"\n  --- datapoints for {dev.name!r} (type {dev.device_type}) ---")
    report: dict[str, Any] = {}
    try:
        configs = await client.async_discover_datapoints(hs_id, dev.id)
    except KermiError as err:
        print(f"    menu walk failed: {err}")
        return report
    print(f"    discovered {len(configs)} datapoints via menu walk")
    report["configs"] = configs
    if not configs:
        return report

    pairs = [(dev.id, c.id) for c in configs if not c.hidden]
    values: list[Any] = []
    for start in range(0, len(pairs), 50):
        values.extend(await client.async_read_values(hs_id, pairs[start : start + 50]))
    report["values"] = values
    by_id = {v.config_id: v for v in values}
    for cfg in configs:
        if cfg.hidden:
            continue
        val = by_id.get(cfg.id)
        raw = val.value if val else "—"
        label = ""
        if val is not None and cfg.possible_values and isinstance(raw, int):
            label = f"  ({cfg.possible_values.get(raw, '?')})"
        name = cfg.well_known_name or ""
        print(f"      {name:<34} {raw!s:>10} {cfg.unit:<5} {cfg.display_name}{label}")
    return report


async def _run(username: str, password: str) -> dict[str, Any]:
    report: dict[str, Any] = {}
    async with aiohttp.ClientSession() as session:
        auth = KermiAuth(session=session, username=username, password=password)
        client = KermiClient(session, auth)

        print("→ Logging in …")
        token = await auth.async_verify_credentials()
        print(f"  access_token : {_mask(token.access_token)}")
        print(f"  refresh_token: {_mask(token.refresh_token or '')}")
        print(f"  expires_in   : ~{int(token.expires_at - time.time())}s")
        print(f"  scope        : {token.scope}")

        if token.refresh_token:
            print("→ Testing refresh_token grant …")
            refreshed = await auth._async_refresh(token.refresh_token)  # noqa: SLF001
            print(f"  refreshed access_token: {_mask(refreshed.access_token)}")

        print("→ WebUser/LoginCurrentUser …")
        print(f"  permissions: {await client.async_login_current_user()}")

        print("→ System/GetHomeServers …")
        home_servers = await client.async_get_home_servers()
        report["home_servers"] = home_servers
        report["systems"] = {}
        for hs in home_servers:
            print(f"\n=== {hs.name} ({hs.id}) online={hs.is_online} ===")
            sysinfo: dict[str, Any] = {}
            report["systems"][hs.id] = sysinfo

            devices = await client.async_get_devices(hs.id)
            sysinfo["devices"] = devices
            print(f"  {len(devices)} devices:")
            for dev in devices:
                print(
                    f"   - type={dev.device_type:<3} {dev.name!r} "
                    f"v{dev.software_version} id={dev.id}"
                )

            sysinfo["enums"] = await client.async_resolve_enums(
                hs.id, ["HeatpumpState", "HeatingCircuitState"]
            )
            print(f"  enums: {json.dumps(sysinfo['enums'], ensure_ascii=False)}")

            sysinfo["datapoints"] = {
                dev.id: await _probe_device(client, hs.id, dev)
                for dev in devices
                if dev.device_type in PROBE_DEVICE_TYPES
            }
    return report


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", metavar="PATH", help="write a full JSON dump")
    args = parser.parse_args()

    _load_dotenv()
    username = os.environ.get("KERMI_USERNAME")
    password = os.environ.get("KERMI_PASSWORD")
    if not username or not password:
        print("Set KERMI_USERNAME and KERMI_PASSWORD (env or .env file).")
        return 2

    try:
        report = asyncio.run(_run(username, password))
    except KermiError as err:
        print(f"\nFAILED: {err.__class__.__name__}: {err}")
        return 1

    if args.dump:
        Path(args.dump).write_text(
            json.dumps(report, default=_json_default, indent=2, ensure_ascii=False)
        )
        print(f"\nWrote full dump to {args.dump}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
