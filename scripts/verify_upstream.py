#!/usr/bin/env python3
"""Fail closed if the pinned Scrapling v0.5 public API differs from this skill."""

from __future__ import annotations

import inspect
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINNED = (ROOT / "UPSTREAM_VERSION").read_text(encoding="utf-8").strip()

MCP_TOOLS = {
    "make_request",
    "browser_fetch_once",
    "browser_open",
    "open_request_session",
    "close_session",
    "list_sessions",
    "browser_save_state",
    "browser_load_state",
    "browser_fetch",
    "session_make_request",
    "browser_screenshot",
    "browser_extract",
    "browser_actions",
    "browser_evaluate",
    "browser_network_requests",
    "browser_network_request",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    installed = version("scrapling")
    require(installed == PINNED, f"installed Scrapling {installed} != pinned {PINNED}")

    import scrapling.fetchers as fetchers
    from scrapling.fetchers import (
        AsyncFetcher,
        AsyncStealthySession,
        Fetcher,
        FetcherSession,
        ProxyRotator,
        StealthyFetcher,
        StealthySession,
    )
    from scrapling.spiders import (
        ContentSpider,
        CrawlRule,
        CrawlSpider,
        LinkExtractor,
        Response,
        SiteToMarkdownSpider,
        Spider,
    )

    require(
        not any(hasattr(fetchers, old) for old in ("DynamicFetcher", "DynamicSession", "AsyncDynamicSession")),
        "legacy Dynamic* browser APIs unexpectedly present: review the v0.5 migration",
    )
    symbols = {
        "Fetcher": Fetcher,
        "AsyncFetcher": AsyncFetcher,
        "FetcherSession": FetcherSession,
        "StealthyFetcher": StealthyFetcher,
        "StealthySession": StealthySession,
        "AsyncStealthySession": AsyncStealthySession,
        "ProxyRotator": ProxyRotator,
        "Spider": Spider,
        "Response": Response,
        "ContentSpider": ContentSpider,
        "SiteToMarkdownSpider": SiteToMarkdownSpider,
        "CrawlSpider": CrawlSpider,
        "CrawlRule": CrawlRule,
        "LinkExtractor": LinkExtractor,
    }
    require(all(symbols.values()), "documented public import unavailable")

    session_params = inspect.signature(FetcherSession).parameters
    require("proxy_rotator" in session_params, "FetcherSession missing proxy_rotator")
    require("follow_redirects" in session_params, "FetcherSession missing follow_redirects")
    require("proxies" in inspect.signature(ProxyRotator).parameters, "ProxyRotator missing proxies")
    require("record_requests" in inspect.signature(StealthySession).parameters,
            "StealthySession missing record_requests network-history option")

    require(hasattr(Spider, "robots_txt_obey"), "Spider missing robots_txt_obey")
    require(hasattr(Fetcher, "get"), "Fetcher.get unavailable")
    require(hasattr(StealthySession, "close_pages"), "StealthySession.close_pages unavailable")
    require(hasattr(Response, "markdown"), "Response.markdown unavailable")
    md_params = inspect.signature(Response.markdown).parameters
    require("main_content_only" in md_params and "css_selector" in md_params,
            "Response.markdown signature changed")

    from scrapling.core.ai import ScraplingMCPServer
    missing = sorted(name for name in MCP_TOOLS if not callable(getattr(ScraplingMCPServer, name, None)))
    require(not missing, f"Scrapling MCP methods missing: {missing}")

    print(f"Scrapling {installed} API verified: {len(symbols)} Python symbols; {len(MCP_TOOLS)} MCP methods")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
