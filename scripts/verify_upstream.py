#!/usr/bin/env python3
"""Verify the pinned Scrapling package exposes the API surface used by this skill."""

from __future__ import annotations

import inspect
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINNED = (ROOT / "UPSTREAM_VERSION").read_text(encoding="utf-8").strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    installed = version("scrapling")
    require(installed == PINNED, f"installed Scrapling {installed} != pinned {PINNED}")

    from scrapling.fetchers import (
        AsyncDynamicSession,
        AsyncFetcher,
        AsyncStealthySession,
        DynamicFetcher,
        DynamicSession,
        Fetcher,
        FetcherSession,
        ProxyRotator,
        StealthyFetcher,
        StealthySession,
    )
    from scrapling.spiders import Response, Spider

    symbols = {
        "Fetcher": Fetcher,
        "AsyncFetcher": AsyncFetcher,
        "FetcherSession": FetcherSession,
        "DynamicFetcher": DynamicFetcher,
        "DynamicSession": DynamicSession,
        "AsyncDynamicSession": AsyncDynamicSession,
        "StealthyFetcher": StealthyFetcher,
        "StealthySession": StealthySession,
        "AsyncStealthySession": AsyncStealthySession,
        "ProxyRotator": ProxyRotator,
        "Spider": Spider,
        "Response": Response,
    }
    require(all(symbols.values()), "one or more documented symbols are unavailable")

    session_params = inspect.signature(FetcherSession).parameters
    require("proxy_rotator" in session_params, "FetcherSession lost proxy_rotator parameter")
    require("follow_redirects" in session_params, "FetcherSession lost follow_redirects parameter")

    proxy_params = inspect.signature(ProxyRotator).parameters
    require("proxies" in proxy_params, "ProxyRotator lost proxies parameter")

    require(hasattr(Spider, "robots_txt_obey"), "Spider lost robots_txt_obey")
    require(hasattr(Fetcher, "get"), "Fetcher.get is unavailable")

    try:
        from scrapling.core.ai import ScraplingMCPServer
    except Exception as exc:  # pragma: no cover - provides a useful CI failure
        raise AssertionError(f"MCP server import failed: {exc}") from exc
    require(ScraplingMCPServer is not None, "ScraplingMCPServer unavailable")

    print(f"Scrapling API surface verified for {installed}: {', '.join(symbols)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
