# Verification matrix — Scrapling 0.5

**Evidence review: 2026-10-21.** PyPI released upstream **0.5**
on 2026-10-17. The existence of CI scripts is *not* evidence that the
current branch passed: check exact workflow run before promoting a status.

| Claim | Status / precise boundary |
| --- | --- |
| Pinned upstream version is 0.5 | VERIFIED from PyPI/tag and UPSTREAM_VERSION |
| Stealthy replaces Dynamic browser classes | VERIFIED upstream migration guide |
| Network history replaces capture_xhr | VERIFIED upstream docs; site-specific capture NOT_PROVEN |
| ContentSpider supports Markdown corpus workflows | VERIFIED upstream docs; real crawl NOT_PROVEN |
| MCP v0.5 exposes 16 named tools, no bulk | VERIFIED upstream docs; Inspector confirmation conditional on green current CI |
| Python imports/parameter assumptions work in pinned wheel | VERIFIED_IN_CI only when quality gate passes |
| MCP stdio initialization/tools/list work | VERIFIED_IN_CI only when MCP black-box passes |
| response.follow method/body/params inheritance removed | VERIFIED upstream migration guide |
| robots.txt fetch error can block crawl with robots_txt_obey=True | VERIFIED upstream migration guide |
| Adaptive relocation guarantees correct business fields | REJECTED — semantics require validation |
| Cleaned Markdown is safe to execute as agent instructions | REJECTED — content remains untrusted |
| Browser works on every target website | NOT_PROVEN without authorized site/runtime E2E |
| Recall local memory module/CLI exists on this PR branch | VERIFIED_IN_REPO, not merged |
| Recall local event/profile logic | VERIFIED_IN_CI only after exact PR SHA tests pass |
| Recall blocks false deletions | SUPPORTED for tested offline cases; real-site run quality NOT_PROVEN |
| Saved robots/terms status equals compliance proof | REJECTED — caller assertion only |
| Memory reduces latency, token spend or commercial cost | NOT_PROVEN; three owned-site benchmark required |
| Recall is an official upstream Scrapling feature | REJECTED — independent companion |

## Authoritative references

- https://pypi.org/project/scrapling/0.5/
- https://github.com/D4Vinci/Scrapling/blob/v0.5/docs/migrating-to-v0.5.md
- https://github.com/D4Vinci/Scrapling/blob/v0.5/docs/ai/mcp-server.md
- https://github.com/D4Vinci/Scrapling/blob/v0.5/docs/ai/building-rag-systems.md
- https://github.com/modelcontextprotocol/inspector/releases/tag/2.8.0

## Verification and release gates

~~~bash
python -m pip install -r requirements-dev.txt
python scripts/validate_markdown.py
python scripts/validate_skill.py
python scripts/verify_upstream.py
~~~

CI also uses MCP Inspector to inspect 16 tools through stdio. This does
not prove authorized browser startup or target-site extraction.
Before production use, exercise realistic browser, HTTP, robots, DOM drift,
checkpoint, schema-validation and error cases. Recheck compatibility when
upstream version, MCP protocol, Python dependencies or target changes.

VERIFIED = source/observation supports *exact* claim; VERIFIED_IN_CI = passed
for the *exact* commit; PARTIAL = missing material proof; NOT_PROVEN = no
production claim; REJECTED = contradicted or insecure absolute statement.

## Recall release evidence (2026-10-23)

- `python -m unittest discover -s tests -p 'test_scrapling_memory.py' -v`
  must pass for the **exact PR SHA** before release claims.
- Offline synthetic 3 sites × 2 passes is a deterministic logic check, not
  a browser crawl of three real sites.
- `runtime/scrapling_memory.py` does not download data and has no hosted
  storage, model-driven semantic search or recurring scheduler.
- Full boundaries: [memory reference](references/memory.md).
