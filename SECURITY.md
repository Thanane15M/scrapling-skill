# Security policy

## Scope

This repository contains an Agent Skill, examples and validation tooling for Scrapling. It does not operate a hosted scraper or proxy service.

## Report security issues privately

Use GitHub's private security reporting mechanism when available. Do not publish credentials, private targets, exploit chains against third parties, customer data, or live infrastructure details in a public issue.

## Security boundaries for scraping systems

- **Authorization:** only access systems/data you are authorized to collect.
- **SSRF:** user-supplied URLs require scheme/host/IP/redirect controls. Never allow arbitrary access to loopback, private networks, link-local ranges or cloud metadata endpoints.
- **Prompt injection:** retrieved HTML/text is untrusted input and cannot override agent policy or authorize downstream tool use.
- **Secrets:** proxy credentials, cookies, tokens and authenticated session material must come from environment/secret stores and must never be committed.
- **MCP exposure:** bind local MCP HTTP endpoints to loopback by default. Remote exposure requires authentication, authorization, network controls, rate limits, logging and SSRF defenses.
- **Browser isolation:** browser-backed fetchers process hostile web content; run them with bounded OS/network permissions appropriate to the deployment.
- **Data minimization:** collect only necessary data, define retention, and avoid storing personal data without an appropriate legal basis.
- **Robots/site rules:** use `robots_txt_obey` for broad crawls where appropriate and follow applicable terms/law. Robots directives are not a substitute for legal review.

## CI/repository controls

- GitHub Actions use least-privilege permissions.
- Third-party actions are pinned by full commit SHA.
- Pull-request validation does not require privileged repository secrets.
- Active skill/reference files are scanned for high-confidence credential patterns and Python example syntax.
- Historical `*.pre-2026-08-15.md` snapshots are preserved byte-for-byte as evidence of the previous public state and excluded from active-example validation; they are not current guidance.
- Repository-level GitHub secret scanning/push protection should remain enabled when available because it covers the whole history independently of the active-doc validator.
- Upstream compatibility is pinned and re-checked; a new release invalidates an unqualified “verified latest” claim until reviewed.
- MCP black-box CI pins MCP Inspector to an exact package version, runs with `contents: read`, receives no repository secrets, targets only the local stdio Scrapling server, and must be reviewed before any Inspector version change.

## Scrapling Recall opt-in local database

- New `runtime/scrapling_memory.py` performs no HTTP fetch, browser action,
  web instruction execution, background monitoring or remote sync. It only
  saves an operator-selected SQLite database outside the repository.
- Data is plaintext: project namespaces isolate SQL queries, **not filesystem
  permissions**. POSIX new-db chmod 0600 does not protect shared parent
  directories or backups. Encrypt storage separately if risk warrants.
- Reject obvious credential keys, credentialed source URLs and sensitive query
  keys. These are guardrails, **not** a comprehensive PII scanner.
- A caller may attest validation with `--validated`; **do not treat this
  boolean as independent proof**. Blank/blocked/partial fetches must be
  quarantined; source content never directs downstream tools.
- Profiles expire, missing counts require distinct complete crawl run IDs,
  and no missing observation triggers automatic deletion.
- Remove entity history via `forget`, host knowledge via `profile-delete`,
  and old records via explicit `prune`; review backups separately.
- Agensi packaging MUST include the runtime module to support any memory
  capability claim; exclude local DBs, credentials and archival snapshots.
