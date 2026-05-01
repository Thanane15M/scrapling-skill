![Claude Skill](https://img.shields.io/badge/Claude-Skill-orange) ![MIT License](https://img.shields.io/badge/License-MIT-green)

# scrapling-skill

BeautifulSoup4 is 784 times slower than Scrapling. That number is from the official benchmark.
Most Python scraping tutorials still recommend it.

This is the first Claude Skill for [Scrapling](https://github.com/D4Vinci/Scrapling) — 22.7k stars, 92% test coverage, native MCP server.
The official docs cover the API. This skill covers what to actually do with it.

## Why this skill exists

Scrapling's self-healing selectors, Cloudflare bypass, and multi-engine architecture aren't obvious from the README.
Knowing which fetcher to pick (Fetcher vs. AsyncFetcher vs. PlayWright vs. StealthyFetcher) requires reading three separate docs pages.
The MCP server integration pattern is undocumented. This skill compresses all of it into one reference.

## What's covered

- **Fetcher selection** — when to use each of the four fetcher types
- **Session management** — persistent sessions, cookie handling, header fingerprinting
- **Self-healing selectors** — CSS and XPath with auto-recovery when sites change
- **Spider architecture** — breadth-first vs. depth-first, rate limiting, retry logic
- **MCP integration** — wiring Scrapling to Claude via the native MCP server
- **CLI usage** — one-off scraping without writing a script
- **BS4 migration** — drop-in replacement patterns for existing scrapers

## Install

```bash
claude skill install https://github.com/Thanane15M/scrapling-skill
```

Or copy `SKILL.md` into `.claude/skills/scrapling-skill/`.

## License

MIT
