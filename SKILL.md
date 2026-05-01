---
name: scrapling
description: >
  Expert Scrapling — framework Python de web scraping adaptatif (22k+ stars) gérant tout depuis une
  requête simple jusqu'à un crawl full-scale avec pause/resume. Utiliser pour : choisir le bon
  fetcher ou session (Fetcher/StealthyFetcher/DynamicFetcher + variantes Session/Async), activer le
  mode self-healing (adaptive=True / auto_save=True), bypass Cloudflare Turnstile, configurer
  ProxyRotator, sessions multi-types dans un spider, streaming de résultats, export JSON/JSONL,
  intégrer le serveur MCP natif avec Claude/agent/Cursor, utiliser la CLI (extract/shell),
  impersonation TLS (chrome/firefox), HTTP/3, migrer depuis BeautifulSoup/Scrapy, déployer via
  Docker. Déclencher aussi pour : "scraper auto-réparant", "sélecteur cassé redesign", "bypass
  anti-bot Python", "session scraping persistante", "crawl pause resume Python", "scrapling
  install", "scrapling MCP", "scrapling spider", "scrapling session", "impersonate chrome scraping".
---

# Scrapling — Framework Python de Scraping Adaptatif

**22.7k stars · 92% test coverage · Python 3.10+**
Docs complètes : https://scrapling.readthedocs.io

---

## Installation

```bash
# Parser seul (sans fetchers)
pip install scrapling

# Avec fetchers + navigateurs (recommandé)
pip install "scrapling[fetchers]"
scrapling install           # télécharge Chromium + dépendances système

# Tout inclus (fetchers + MCP + shell)
pip install "scrapling[all]"

# À la carte
pip install "scrapling[ai]"     # MCP server
pip install "scrapling[shell]"  # CLI shell + commande extract

# Docker (all extras + browsers)
docker pull pyd4vinci/scrapling
docker pull ghcr.io/d4vinci/scrapling:latest
```

---

## Architecture — Choisir le bon outil

### Fetchers (one-shot) vs Sessions (persistantes)

| Besoin | One-shot | Session persistante | Async session |
|--------|----------|--------------------|----|
| HTTP rapide | `Fetcher` | `FetcherSession` | `AsyncFetcher` |
| Bypass Cloudflare / anti-bot | `StealthyFetcher` | `StealthySession` | `AsyncStealthySession` |
| JS lourd / SPA | `DynamicFetcher` | `DynamicSession` | `AsyncDynamicSession` |

> **Règle** : utilise les classes Session pour tout crawl multi-pages (cookies partagés, état navigateur conservé). Les one-shot ouvrent/ferment un browser à chaque appel.

---

## Fetchers — Exemples concrets

### HTTP rapide avec impersonation TLS

```python
from scrapling.fetchers import Fetcher, FetcherSession

# One-shot
page = Fetcher.get('https://quotes.toscrape.com/')

# Session persistante avec fingerprint Chrome
with FetcherSession(impersonate='chrome') as session:
    page1 = session.get('https://site.com/page1', stealthy_headers=True)
    page2 = session.get('https://site.com/page2', impersonate='firefox135')

# HTTP/3
with FetcherSession(http3=True) as session:
    page = session.get('https://site.com/')
```

### Bypass Cloudflare Turnstile

```python
from scrapling.fetchers import StealthyFetcher, StealthySession

# One-shot
page = StealthyFetcher.fetch('https://nopecha.com/demo/cloudflare')

# Session persistante (browser ouvert en continu)
with StealthySession(headless=True, solve_cloudflare=True) as session:
    page = session.fetch('https://protected-site.com', google_search=False)
    data = page.css('#content a').getall()
```

### Sites SPA / JavaScript lourd

```python
from scrapling.fetchers import DynamicFetcher, DynamicSession

with DynamicSession(headless=True, network_idle=True) as session:
    page = session.fetch('https://react-app.com', load_dom=False)
    data = page.xpath('//span[@class="text"]/text()').getall()
```

---

## Self-Healing Selectors (Adaptive)

```python
# Phase 1 — première exécution : sauvegarde la signature de l'élément
products = page.css('.product-card', auto_save=True)

# Phase 2 — après redesign du site : retrouve l'élément par similarité
products = page.css('.product-card', adaptive=True)

# Ou au niveau du fetcher entier
StealthyFetcher.adaptive = True
page = StealthyFetcher.fetch('https://example.com', headless=True)
```

---

## Extraction & Navigation

```python
# CSS (pseudo-éléments Scrapy/Parsel compatibles)
titles = page.css('h2.title::text').getall()
href   = page.css('a::attr(href)').get()

# XPath
price = page.xpath('//span[@class="price"]/text()').get()

# Style BeautifulSoup
items = page.find_all('div', class_='product')
items = page.find_all(['div', 'article'], class_='card')
items = page.find_all(class_='product')

# Recherche par texte
btn = page.find_by_text('add to cart', tag='button')

# Navigation DOM
parent   = element.parent
siblings = element.siblings
children = element.children
below    = element.below_elements()
similar  = element.find_similar()

# Chaînage
text = page.css('.quote')[0].css('.text::text').get()

# Génération auto de sélecteurs
css_sel   = element.generate_css_selector
xpath_sel = element.generate_xpath_selector
```

---

## Spiders — Crawl Full-Scale

### Spider basique avec export

```python
from scrapling.spiders import Spider, Request, Response

class QuotesSpider(Spider):
    name = "quotes"
    start_urls = ["https://quotes.toscrape.com/"]
    concurrent_requests = 10

    async def parse(self, response: Response):
        for quote in response.css('.quote'):
            yield {
                "text":   quote.css('.text::text').get(),
                "author": quote.css('.author::text').get(),
            }
        next_page = response.css('.next a')
        if next_page:
            yield response.follow(next_page[0].attrib['href'])

result = QuotesSpider().start()
print(f"Scraped {len(result.items)} items")
result.items.to_json("output.json")
result.items.to_jsonl("output.jsonl")
```

### Multi-Session Spider

```python
from scrapling.spiders import Spider, Request, Response
from scrapling.fetchers import FetcherSession, AsyncStealthySession

class MultiSessionSpider(Spider):
    name = "multi"
    start_urls = ["https://example.com/"]

    def configure_sessions(self, manager):
        manager.add("fast",    FetcherSession(impersonate="chrome"))
        manager.add("stealth", AsyncStealthySession(headless=True), lazy=True)

    async def parse(self, response: Response):
        for link in response.css('a::attr(href)').getall():
            if "protected" in link:
                yield Request(link, sid="stealth")
            else:
                yield Request(link, sid="fast", callback=self.parse)
```

### Pause & Resume

```python
# Lancer avec checkpoint
QuotesSpider(crawldir="./crawl_data").start()
# Ctrl+C → sauvegarde auto · Relancer → reprend depuis le checkpoint
```

### Streaming temps réel

```python
async for item in spider.stream():
    await save_to_db(item)   # reçoit les items au fil de l'eau
```

---

## ProxyRotator + Blocage ads

```python
from scrapling import ProxyRotator
from scrapling.fetchers import StealthyFetcher

rotator = ProxyRotator(proxies=[
    'http://user:pass@proxy1:8080',
    'http://user:pass@proxy2:8080',
])

page = StealthyFetcher.fetch(
    'https://target.com',
    proxy=rotator.next(),
    block_ads=True     # bloque ~3500 domaines
)
```

> Pour Cloudflare entreprise : proxies résidentiels (BirdProxies, Evomi, DataImpulse).
> Pour Akamai/DataDome/Kasada/Incapsula : API [Hyper Solutions](https://hypersolutions.co).

---

## MCP Server — Intégration Claude / agent / Cursor

```bash
pip install "scrapling[ai]"
```

**Avantage tokens** : l'IA reçoit uniquement les données extraites, pas le HTML brut.

### server.json

```json
{
  "mcpServers": {
    "scrapling": {
      "command": "python",
      "args": ["-m", "scrapling.mcp"]
    }
  }
}
```

Docs MCP : https://scrapling.readthedocs.io/en/latest/ai/mcp-server/

---

## CLI

```bash
# Shell interactif IPython (debug sélecteurs, curl→Scrapling, preview dans browser)
scrapling shell
scrapling shell https://example.com

# Extraction directe vers fichier (.txt / .md / .html)
scrapling extract get 'https://example.com' output.md
scrapling extract get 'https://example.com' output.txt --css-selector '#content' --impersonate 'chrome'
scrapling extract fetch 'https://example.com' output.md --no-headless
scrapling extract stealthy-fetch 'https://cf-site.com' out.html --solve-cloudflare
```

---

## Benchmarks

| Librairie | 5000 éléments | vs Scrapling |
|-----------|--------------|-------------|
| **Scrapling** | **2.02 ms** | 1.0x |
| Parsel/Scrapy | 2.04 ms | ~1x |
| Raw Lxml | 2.54 ms | 1.3x |
| PyQuery | 24.17 ms | ~12x |
| Selectolax | 82.63 ms | ~41x |
| BS4 + lxml | 1584 ms | **~784x** |
| BS4 + html5lib | 3391 ms | ~1679x |

**Adaptive finding** : Scrapling 2.39ms vs AutoScraper 12.45ms (5.2x plus rapide).

---

## Parser standalone (sans réseau)

```python
from scrapling.parser import Selector

page = Selector("<html>...</html>")
titles = page.css('h2::text').getall()
```

---

## Références

→ `references/patterns.md` — Patterns d'intégration stack agent/n8n/Neon/content-pipeline
