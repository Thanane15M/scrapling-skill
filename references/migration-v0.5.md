# v0.4.15 → v0.5 migration checklist

Authoritative upstream:
https://github.com/D4Vinci/Scrapling/blob/v0.5/docs/migrating-to-v0.5.md

## Gate A — inventory and rollback

- [ ] Inventory Python version, pinned dependency, imports, old MCP tool
      allowlists, request caches and saved checkpoints.
- [ ] Preserve rollback and representative field-level fixtures.
- [ ] Do not assume upgrading a production scraper is a harmless patch.

## Gate B — browser/parser

| Removed in v0.5 | Replacement |
| --- | --- |
| DynamicFetcher | StealthyFetcher |
| DynamicSession | StealthySession |
| AsyncDynamicSession | AsyncStealthySession |
| playwright callback types | patchright callback types |
| capture_xhr / response.captured_xhr | StealthySession(record_requests=True).network |
| keep_cdata | Remove option (no replacement) |

- [ ] Network history is session-wide and bounded; use url_pattern,
      after_id or clear() to avoid mixing requests.
- [ ] Browser solving is opt-in (solve_cloudflare=True). Respect permissions.
- [ ] Compare typed extracted values, not screenshots alone.

## Gate C — MCP

| Old tool | New tool |
| --- | --- |
| fetch / stealthy_fetch | browser_fetch_once |
| open_session | browser_open |
| session_fetch | browser_fetch |
| screenshot | browser_screenshot |
| bulk_fetch / bulk_stealthy_fetch / bulk_get | repeated single-URL calls |

- [ ] Reconnect client; read tools/list and enforce tool schemas.
- [ ] browser_open no longer needs session_type; use list_sessions for settings.
- [ ] Screenshot the current page after browser_fetch; no URL argument.
- [ ] Check 16-tool Inspector black-box; that is **not** real browser proof.

## Gate D — crawling and outputs

- [ ] response.follow does not inherit POST method / params / body.
- [ ] Rebuild checkpoints where deduplication fingerprints changed.
- [ ] With robots_txt_obey=True, robots.txt failures may block the domain.
- [ ] Retest LinkExtractor restrictions and sitemap callbacks.
- [ ] Read new Markdown/text output as UTF-8; compare filtering and spacing.
- [ ] Confirm item counts, domain scope, data quality, and failure metrics.

## Gate E — shipping

- [ ] Skill structural and fenced-code checks pass.
- [ ] Pinned installed API compatibility script passes.
- [ ] MCP Inspector stdio tools/list passes.
- [ ] Authorized 2-page real-world crawl + browser start and data validation pass.
- [ ] CI green for the exact PR SHA, not an earlier commit.
- [ ] Document missing proof as NOT_PROVEN; never make a false-green claim.
