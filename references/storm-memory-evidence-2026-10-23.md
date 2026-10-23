# Scrapling Recall — STORM research synthesis (2026-10-23)

**Approach:** multi-perspective research, sourced adversarial questions and synthesis inspired by [Stanford STORM](https://github.com/stanford-oval/storm). This note **does not** claim Stanford's autonomous STORM software was executed. All claims are scoped to public references and the verified GitHub baseline.

## Reality lock

- Independent skill: [Thanane15M/scrapling-skill](https://github.com/Thanane15M/scrapling-skill), `main` commit `3116d1dd8720b3a393c040b29f743555e40b21dc` as observed 2026-10-23. Its Oct 21 quality and MCP black-box workflows passed on that exact SHA; they did **not** verify operation against target websites.
- Upstream: [D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling), [PyPI release 0.5](https://pypi.org/project/scrapling/0.5/) of 2026-10-17. Official skill exists and documents adaptive selectors, sessions, spiders and MCP. The library already persists selector fingerprint memory (SQLite by default) and crawl state. Therefore **memory is not an invention**, nor proof of competitive exclusivity.

## Perspectives and question-led synthesis

| Perspective | Adversarial question | Conclusion |
| --- | --- | --- |
| Framework maintainer | Is the feature already in the upstream? | Adaptive DOM SQLite / crawler checkpoint yes; business-field provenance and per-site recipe ledger **not established** by upstream evidence reviewed |
| Operator | How to avoid a 403 or CAPTCHA becoming a false “zero result”? | Quarantine unverified/partial/blocked runs; never poison trusted baseline |
| Data quality | What counts as a real change? | Compare normalized typed fields, not raw HTML; detect move only with operator-provided stable identity |
| Security/privacy | Can memory persist cookies, tokens, personal data? | Never store raw network capture; use explicit local SQLite, namespaces, URL/query checks, erasure; caveat: cannot guarantee PII detection |
| Marketplace buyer | What would be distinctive against mature free and paid offerings? | Evidence-first local companion, inspectable database, no required API key; commercial demand remains unmeasured |
| Product owner | What does the first defensible release contain? | Narrow opt-in local memory, six statuses, expiry, idempotent missing runs, offline tests and verification boundaries |

## Competitive checks

- [Crawlee Python storage](https://crawlee.dev/python/docs/guides/storages): persistent queues, datasets and KV; basic persistence is not unique.
- [Web Scraper](https://webscraper.io/blog/incremental-web-scraping-and-change-detection): field-level incremental records and change taxonomies; single-run absence is insufficient to confirm deletion.
- [Firecrawl monitor](https://www.firecrawl.dev/monitor): scheduled change monitoring and notifications; stronger hosted convenience but API-key/deployment trade-offs.
- [Kadoa](https://www.kadoa.com/blog/how-ai-is-changing-web-scraping-2026): reports a customer spent 40% engineering time maintaining scrapers; **vendor anecdote**, not verified market prevalence.
- [Agensi](https://www.agensi.io/learn/best-claude-code-skills-2026): broad free skill distribution suggests low-friction discovery; install rankings are dynamic and **not** proof of sales or willingness-to-pay.

## Findings graded

- **VERIFIED:** upstream selector memory exists; independent skill was pinned to 0.5 on audited SHA; mature competitors already store crawler state and/or detect change.
- **SUPPORTED DESIGN:** separate extraction recipe profile, versioned business-field records, explicit provenance and fail-closed “uncertain” state are technically coherent and testable.
- **NOT_PROVEN:** this memory reduces operating cost, maintains correctness on real websites, creates user adoption or receives paid demand.
- **REJECTED CLAIMS:** “first scraping skill with memory”; “AI extracts error-free”; “tested on production sites” based only on offline fixtures.

## Acceptance study before promotion

Test three **owned** sites, two successful passes each, include one deliberate DOM change, one blocked/partial response, and one moved stable entity. Compare extraction without recall vs with recall on request count, median/p95 latency, correct field yield, false change rate, confirmed-missing error rate and total engineering intervention. Publish exact test conditions and observed results, not projections. Distribute free first if marketing evidence remains weak; do not submit a capability claim before the runtime + tests are actually in the Agensi ZIP.
