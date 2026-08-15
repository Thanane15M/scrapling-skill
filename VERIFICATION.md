# Verification matrix

Last evidence review: **2026-08-15**.
Pinned upstream version: **Scrapling 0.4.14**.

| Claim | Status | Evidence / boundary |
|---|---|---|
| Scrapling 0.4.14 is the pinned compatibility target | VERIFIED | Upstream GitHub release `v0.4.14`, published 2026-08-10; `UPSTREAM_VERSION` pins the repository target. |
| `ProxyRotator` is importable from `scrapling.fetchers` | VERIFIED_IN_CI when green | Current upstream API docs plus `scripts/verify_upstream.py`. |
| `FetcherSession` exposes `proxy_rotator` and safe redirect controls | VERIFIED_IN_CI when green | Current upstream API docs plus signature introspection. |
| Spider exposes `robots_txt_obey` | VERIFIED_IN_CI when green | Current upstream spider docs plus attribute introspection. |
| `scrapling mcp` and streamable HTTP mode exist | VERIFIED | Current upstream MCP documentation. |
| Every browser/anti-bot flow works on every target site | NOT_PROVEN | Target-site behavior, browser dependencies, network policy and authorization vary. |
| Adaptive selector relocation is semantically correct for critical data | NOT_PROVEN by relocation alone | Requires domain validation after match. |
| Scraped web content is safe to pass directly to an autonomous agent | REJECTED | Treat web content as untrusted input; prompt injection and SSRF must be considered. |

## Authoritative upstream references

- Releases: `https://github.com/D4Vinci/Scrapling/releases`
- Documentation: `https://scrapling.readthedocs.io/en/latest/`
- Proxy rotation: `https://scrapling.readthedocs.io/en/latest/api-reference/proxy-rotation.html`
- Spider robots behavior: `https://scrapling.readthedocs.io/en/latest/spiders/getting-started.html`
- MCP server: `https://scrapling.readthedocs.io/en/latest/ai/mcp-server.html`

## Re-verification triggers

Compatibility returns to `NOT_PROVEN` until checked when:

- PyPI/GitHub latest release differs from `UPSTREAM_VERSION`;
- documented import paths or signatures change;
- Spider lifecycle or adaptive-selector behavior changes;
- MCP transport/CLI flags change;
- security-relevant defaults such as redirect handling change.

## Evidence vocabulary

- `VERIFIED` — authoritative upstream evidence directly supports the scoped claim.
- `VERIFIED_IN_CI` — a deterministic repository check also verifies the installed API surface.
- `PARTIAL` — some evidence exists, but a material runtime property remains untested.
- `NOT_PROVEN` — do not state the claim as fact for the target environment.
- `REJECTED` — claim is intentionally not supported because it is unsafe or too broad.
