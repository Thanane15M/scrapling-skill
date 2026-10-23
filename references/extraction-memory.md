# Scrapling Memory v1 — opt-in extraction memory

This is an **independent integration**, not part of official Scrapling and not a general-purpose agent memory. Upstream Scrapling already remembers adaptive element signatures (SQLite) and has crawl checkpointing. This additive layer remembers **validated extraction outcomes**, not arbitrary web content.

## Guarantees and limits

- Python standard library only, SQLite file on local disk; never connects to a paid service.
- Profiles per **namespace + domain**: last validated HTTP/browser/API mode, selectors, timestamp and TTL (14 days default). Expired profiles are not used. Profiles are hints, **never authoritative**.
- Observations by **namespace + domain + stable record_key**: hashes of explicitly selected scalar fields, stripped source URL, time, change classification. No HTML or field values are saved. Hashes are **not anonymization** (guessable low-entropy values can be inferred); avoid regulated/sensitive fields unless authorized.
- Changes: `new`, `unchanged`, `modified`, `moved`, `missing`, `uncertain`. Changed field names are returned without raw values. A move is a source-path change with identical fields. A simultaneous path/content change reports `modified`.
- Missing requires **3 separate, completed and validated runs** by default. Blocked pages, failed robots requests, ambiguous selectors, invalid fields and HTTP failures must pass `verified=False` or `crawl_verified=False`; they **cannot** become success or evidence of deletion. `missing` never authorizes deletion.
- Every accepted observation produces a provenance receipt; receipt metadata for robots and terms is supplied by caller and must be truthful (default `unknown`). It is not a compliance certification.
- Does not fetch URLs, scan DNS, manage authentication, or enforce website permissions. The **caller** still needs SSRF, redirect, resource-limit and prompt-injection defenses documented in [SECURITY.md](../SECURITY.md). Do not expose DB to users without authorization.
- No automatic external memory sync. Production persistence requires a stable writable volume, access controls, backup, and retention/deletion policy. Do not commit SQLite files.

## Minimal usage

```python
from scripts.extraction_memory import ExtractionMemory

with ExtractionMemory(".local/scrapling-memory.sqlite", namespace="my-project") as memory:
    profile = memory.get_profile("https://example.com/product")
    # Choose fetcher; validate results independently, including known block markers.
    memory.save_profile("https://example.com/product", "http", {"price": ".price"}, ttl_days=14)
    result = memory.observe(
        "https://example.com/product?id=1", "product-1",
        {"price": "€15", "stock": "available"},
        verified=True, scrapling_version="0.5", skill_version="memory-v1",
        robots_reviewed="checked 2026-10-23", terms_reviewed="unknown")
    print(result)  # new / unchanged / modified / moved
    print(memory.history("https://example.com/product", "product-1"))
```

Before producing `verified=True`, validate HTTP outcome, extraction schema, semantic correctness, freshness, absence of block/captcha pages, and source authorization. Never auto-trust a persisted selector.

## Offline check

```bash
python -m unittest discover -s tests -v
```

## Required real-world evaluation (NOT YET PROVEN)

Compare this optional layer against the same Scrapling skill **without** it on three authorized sites, two passes each (plus a controlled DOM change and a blocked run). Measure request count, elapsed time, false changes, missed changes, recovery rate, and PII/secret leakage. Stop/reassess if it does not reduce work or introduces false confidence. Local unit tests do **not** prove live browser/site behavior.

## Agensi distribution

Do **not** ship this as a skill-only ZIP: memory needs `scripts/extraction_memory.py` and its execution permission. The old proposed ZIP file list is superseded for the memory edition. Submit the ZIP only after CI and live-site evaluation. Declare local SQLite writes, persistence location and retention in marketplace metadata.
