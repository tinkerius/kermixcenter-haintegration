#!/usr/bin/env bash
# PostToolUse hook: ruff-format a Python file right after Claude edits it.
# Silently does nothing when ruff is unavailable or the file isn't Python.

command -v ruff >/dev/null 2>&1 || exit 0

file_path="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))' 2>/dev/null)"

[[ "${file_path}" == *.py && -f "${file_path}" ]] || exit 0

ruff format --quiet "${file_path}" || true
