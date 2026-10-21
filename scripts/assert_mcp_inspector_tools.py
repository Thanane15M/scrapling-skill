#!/usr/bin/env python3
"""Assert MCP Inspector tools/list exposes the complete pinned v0.5 tool contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXPECTED = {
    "make_request", "browser_fetch_once", "browser_open", "open_request_session",
    "close_session", "list_sessions", "browser_save_state", "browser_load_state",
    "browser_fetch", "session_make_request", "browser_screenshot", "browser_extract",
    "browser_actions", "browser_evaluate", "browser_network_requests", "browser_network_request",
}

REMOVED = {"fetch", "stealthy_fetch", "bulk_fetch", "bulk_stealthy_fetch",
           "bulk_get", "open_session", "session_fetch", "screenshot"}


def tool_names(value: object) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        tools = value.get("tools")
        if isinstance(tools, list):
            for item in tools:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    names.add(item["name"])
        for nested in value.values():
            names.update(tool_names(nested))
    elif isinstance(value, list):
        for nested in value:
            names.update(tool_names(nested))
    return names


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: assert_mcp_inspector_tools.py <inspector-json>")

    raw = Path(sys.argv[1]).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"MCP Inspector did not emit valid JSON: {exc}") from exc

    names = tool_names(payload)
    missing = EXPECTED - names
    unexpected_legacy = REMOVED & names
    if missing or unexpected_legacy:
        raise AssertionError(
            f"Scrapling v0.5 MCP contract failed: missing={sorted(missing)} "
            f"removed_tools_still_exposed={sorted(unexpected_legacy)} observed={sorted(names)}"
        )

    print(f"MCP Inspector tools/list OK: {len(EXPECTED)} required v0.5 tools observed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
