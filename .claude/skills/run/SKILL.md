---
name: run
description: Launch Home Assistant with the kermixcenter integration in this devcontainer to see a change working against the real Kermi portal.
---

# Run Home Assistant with the integration

1. Dependencies: `scripts/setup` (once; the devcontainer runs it on create).
2. Start HA in the background: `scripts/develop` — it creates `config/` on first run, sets
   `PYTHONPATH` so `custom_components/kermixcenter` is loaded, and runs `hass --debug` on
   <http://localhost:8123>. Startup takes ~30–60 s; wait for `Home Assistant initialized` in
   the log.
3. First run only: complete HA onboarding in the browser, then Settings → Devices & Services →
   Add Integration → "Kermi X-Center" with a real portal account (the user's own; ask them —
   never read `.env` or `config/.storage/` yourself).
4. After code changes: restart `scripts/develop` (Python changes are not hot-reloaded);
   a config-entry reload is enough only for options changes.
5. Check `config/home-assistant.log` (or the terminal output) for `kermixcenter` errors and
   the entities under the Kermi devices.

Without HA, API-level behaviour can be checked with `python3 scripts/kermi_probe.py`.
