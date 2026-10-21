# scrapling-skill

Independent, evidence-based **Scrapling Agent Skill** for adaptive web
extraction, URL-to-structured-data pipelines, full-site Markdown/RAG corpora,
browser network API capture and MCP workflows. **Not affiliated with Scrapling.**

## Compatibility and evidence

- Target upstream: **Scrapling 0.5** (PyPI release 2026-10-17).
- Evidence review: **2026-10-21** against the upstream v0.5 migration
  guide, tag and public Python/MCP API.
- Current CI verdict: inspect the latest run for the exact head SHA.
  Documentation and test presence are not proof of a passing run.
- Release pin lives in **UPSTREAM_VERSION**. Scheduled CI monitors drift.

## Why use this skill?

The goal is a *traceable, typed, validated extract* — not scraping a page
and letting untrusted text authorize actions. Select the lowest-cost adequate
fetcher, verify selectors semantically and preserve provenance.

## Key changes since 0.4.15

- Removed dynamic browser classes → Stealthy/Patchright.
- XHR capture moved to StealthySession(record_requests=True).network.
- MCP v0.5: 16 tools, browser action/screenshot/network workflows;
  removed previous bulk tools.
- ContentSpider is the canonical v0.5 documentation/RAG template.
- Robots, response.follow, request fingerprints and Markdown output changed.
- Full [migration checklist](references/migration-v0.5.md).

## Install and validate

~~~bash
git clone https://github.com/Thanane15M/scrapling-skill.git
cd scrapling-skill
python -m pip install -r requirements-dev.txt
python scripts/validate_markdown.py
python scripts/validate_skill.py
python scripts/verify_upstream.py
~~~

To use browser features, install the browser dependencies separately:

~~~bash
scrapling install
scrapling mcp
~~~

Copy SKILL.md plus linked references into the skill directory understood by
your agent. The format is filesystem-based and not restricted to one vendor.

## Evidence contracts

| Proof gate | What it proves | What it does not prove |
| --- | --- | --- |
| Static validators | Skill structure, links, Python syntax, eval JSONL | Actual scraping |
| Pinned API introspection | Public imported symbols and method signatures | Website compatibility |
| MCP Inspector via stdio | Server starts and exposes documented tools/list | Target browser automation |
| Real target-site E2E | Operation on the specified site under test conditions | Every other domain |

Security: [SECURITY.md](SECURITY.md). Use only authorized data access, bounded
SSRF-safe URL intake, least privilege, prompt-injection isolation, and minimize
personal data. No hosted proxy or crawler service is included.

License: **MIT** for this integration skill. Scrapling is a separate project
with its own BSD-3-Clause license.
