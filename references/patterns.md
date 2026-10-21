# Scrapling v0.5 integration patterns

All code assumes upstream **0.5**. For breaking changes use
[migration-v0.5.md](migration-v0.5.md).

## HTTP static extraction

~~~python
from scrapling.fetchers import Fetcher

page = Fetcher.get("https://example.com/")
title = page.css("title::text").get("").strip()
if not title:
    raise ValueError("missing title")
record = {"url": page.url, "title": title}
~~~

Prefer documented APIs when they satisfy the request.

## Markdown for a sourced article or RAG record

~~~python
from scrapling.fetchers import Fetcher

page = Fetcher.get("https://example.com/article")
markdown = page.markdown(main_content_only=True)
selected = page.markdown(css_selector="article")
~~~

Hidden-content stripping is not a security boundary for tool execution.
Preserve URL/time provenance and verify factual attribution.

## Shared HTTP state / optional proxies

~~~python
from scrapling.fetchers import FetcherSession, ProxyRotator

rotator = ProxyRotator(["http://proxy.example:8080"])
with FetcherSession(proxy_rotator=rotator) as session:
    page = session.get("https://example.com/")
~~~

Keep credentials outside code. Rotate only where legitimate and permitted.

## Adaptive selectors with semantic checks

~~~python
from scrapling.fetchers import Fetcher

page = Fetcher.get("https://example.com/catalogue")
page.css(".price", auto_save=True)
current = page.css(".price", adaptive=True)
if not current:
    raise ValueError("selector drift: no price")
raw = current.css("::text").get("").strip()
if not raw:
    raise ValueError("relocated price empty")
# Validate expected currency, locale, numeric range and source.
~~~

## Patchright browser and network API capture

~~~python
from scrapling.fetchers import StealthySession

with StealthySession(record_requests=True) as session:
    page = session.fetch("https://example.com/app", network_idle=True)
    for response in session.network.search(url_pattern=r"/api/", limit=None):
        print(response.url, response.status)
    session.close_pages()
~~~

Network recordings may include PII; protect retention and tool scopes.
History caps mean absence of a body is not absence of a request.

## Documentation corpus via ContentSpider

~~~python
from scrapling.spiders import ContentSpider

class DocsSpider(ContentSpider):
    name = "docs"
    start_urls = ["https://example.com/docs/"]
    allowed_domains = {"example.com"}
    robots_txt_obey = True
    max_pages = 100
    output_dir = "corpus"
    concurrent_requests = 4
    download_delay = 1.0

result = DocsSpider().start()
result.items.to_jsonl("corpus.jsonl")
~~~

Robots errors can block the domain in 0.5: report blocked, not empty success.

## v0.5 follow() request semantics

~~~python
from scrapling.spiders import Response, Spider

class PagesSpider(Spider):
    name = "pages"
    start_urls = ["https://example.com/"]

    async def parse(self, response: Response):
        for href in response.css("a::attr(href)").getall():
            yield response.follow(href, callback=self.parse)
        # For POST pagination explicitly pass method and body:
        # yield response.follow("/next", method="POST", json={"page": 2})
~~~

## MCP and CLI

~~~bash
python -m pip install "scrapling[ai]==0.5"
scrapling install
scrapling mcp
scrapling extract get "https://example.com/article" article.md --ai-targeted
scrapling extract fetch "https://example.com/app" page.md --ai-targeted
~~~

For browser MCP: browser_open → browser_fetch → browser_extract / actions
→ browser_screenshot → close_session. Discover names with tools/list.
Legacy bulk tools are removed, screenshot does not navigate.

## Untrusted URL operational boundary

Input URL → scheme/host allowlist → DNS/IP/redirect guard (SSRF) →
request budget → content-type and byte limits → extraction → typed validation
→ source receipt → untrusted agent context → human gate for consequential
actions. Log error class, selector yield, source URL and actual dependency.
