# Scrapling Recall — evidence-first extraction skill

![Scrapling Recall independent mark](assets/scrapling-recall-mark.svg)


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


## Scrapling Recall — optional local memory (preview)

**Scraping that remembers its extraction evidence, not a general agent brain.**
The new [standalone Python module](runtime/scrapling_memory.py) attaches a
local, opt-in SQLite history and site extraction profiles to the independent
skill. It **does not** replace upstream adaptive-selector memory or spider
checkpoints; it makes no external requests and needs no API key.

- Host/project scoped extraction profiles with TTL and revalidation warnings.
- Provenance receipts (source URL, UTC, SHA-256 of typed fields, extractor and
  pinned versions) and deduplicated business-field snapshots.
- Six classes: `new`, `unchanged`, `changed`, `moved`, `missing`, `uncertain`.
- Incomplete/blocked/unverified runs cannot poison previous valid data.
  Missing confirmation requires two distinct completed crawl run IDs; **nothing
  is ever automatically deleted**.
- Explicit opt-in, manual review, retention/erasure and offline tests.
  No scheduling, vector search, hosted service or live-site proof included.

[Runtime instructions and data boundaries](references/memory.md) ·
[Research/competitive evidence](references/storm-memory-evidence-2026-10-23.md).

### Minimal use

~~~bash
# After separately validating a successful Scrapling extraction into typed JSON:
python runtime/scrapling_memory.py --db ./private/recall.sqlite \
  --namespace demo observe --url https://example.org/products/42 \
  --file extraction.json --extractor catalogue-v1 --validated
python -m unittest discover -s tests -p 'test_scrapling_memory.py' -v
~~~

**Evidence status:** offline deterministic tests are not a real 3-site
benchmark, and no time/cost reduction, adoption, or legal compliance is claimed.
For Agensi, include `runtime/scrapling_memory.py` in the ZIP or do not advertise
functional memory; do not submit until the QA gate and package audit.

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
