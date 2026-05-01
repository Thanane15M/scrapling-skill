# Scrapling — Patterns Stack agent / n8n / Neon / content-pipeline

## 1. Monitoring de prix avec alerte Telegram

```python
from scrapling.fetchers import StealthySession
import asyncio, httpx

TELEGRAM_TOKEN = "..."
CHAT_ID = "REDACTED_CHAT_ID"  # ton chat_id agent

async def alert(msg: str):
    async with httpx.AsyncClient() as c:
        await c.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                     json={"chat_id": CHAT_ID, "text": msg})

async def monitor_price(url: str, selector: str, threshold: float):
    with StealthySession(headless=True, solve_cloudflare=True) as session:
        while True:
            page = session.fetch(url, network_idle=True)
            el = page.css(selector, adaptive=True)
            if el:
                price = float(el.text.replace('€','').replace(',','.').strip())
                if price <= threshold:
                    await alert(f"🔔 Prix cible : {price}€\n{url}")
            await asyncio.sleep(3600)
```

---

## 2. Crawl multi-pages → Neon PostgreSQL (FastAPI sur Elysium VPS)

Endpoint FastAPI à déployer sur `REDACTED_HOST` :

```python
from fastapi import FastAPI
from scrapling.fetchers import Fetcher, StealthyFetcher
from scrapling.spiders import Spider, Response
import asyncpg

app = FastAPI()
NEON_DSN = "postgresql://..."

@app.post("/scrape/batch")
async def scrape_batch(payload: dict):
    """
    payload: { url, selector, stealth=False, adaptive=False }
    """
    url      = payload["url"]
    selector = payload["selector"]
    stealth  = payload.get("stealth", False)
    adaptive = payload.get("adaptive", False)

    fetcher = StealthyFetcher if stealth else Fetcher
    page    = fetcher.fetch(url, block_ads=True) if stealth else fetcher.get(url)

    results = [
        {"text": el.text, "href": el.attrib.get("href", "")}
        for el in page.css(selector, adaptive=adaptive, auto_save=not adaptive)
    ]

    conn = await asyncpg.connect(NEON_DSN)
    await conn.executemany(
        "INSERT INTO scraped_data (url, selector, text, href, scraped_at) "
        "VALUES ($1, $2, $3, $4, NOW()) ON CONFLICT DO NOTHING",
        [(url, selector, r["text"], r["href"]) for r in results]
    )
    await conn.close()

    return {"count": len(results), "data": results}
```

**Appel depuis n8n** :
- Nœud HTTP Request → POST `http://REDACTED_HOST:PORT/scrape/batch`
- Body : `{"url": "...", "selector": ".price", "stealth": true}`

---

## 3. Spider de veille BTP Mayotte → content-pipeline Pipeline

```python
from scrapling.spiders import Spider, Response
from scrapling.fetchers import FetcherSession
import httpx

content-pipeline_ENDPOINT = "http://REDACTED_HOST:PORT/api/content/ingest"

class BTPVeilleSpider(Spider):
    """
    Scrape sources BTP/actualités Mayotte et injecte dans content-pipeline
    pour scoring [internal-framework] et publication automatisée.
    """
    name = "btp_veille"
    start_urls = [
        "https://www.batiactu.com/",
        "https://mayottehebdo.com/",
        "https://outremers360.com/",
    ]
    concurrent_requests = 3
    download_delay = 2.0  # politesse

    def configure_sessions(self, manager):
        manager.add("http", FetcherSession(impersonate="chrome", stealthy_headers=True))

    async def parse(self, response: Response):
        for article in response.css('article', auto_save=True):
            title   = article.css('h2::text, h3::text', adaptive=True).get('').strip()
            excerpt = article.css('.excerpt::text, p::text', adaptive=True).get('').strip()
            url     = article.css('a::attr(href)', adaptive=True).get('')

            if title and len(title) > 15:
                item = {
                    "title":   title,
                    "excerpt": excerpt,
                    "url":     url,
                    "source":  response.url,
                    "pipeline": "content-pipeline",
                }
                yield item

    async def process_item(self, item: dict):
        """Hook post-extraction → push vers content-pipeline FastAPI"""
        async with httpx.AsyncClient() as c:
            await c.post(content-pipeline_ENDPOINT, json=item)

# Lancer avec pause/resume
BTPVeilleSpider(crawldir="./btp_crawl").start()
```

---

## 4. Commande agent Telegram → Scrapling MCP

Workflow : `/scrape <url> <selector>` dans Telegram → agent → MCP Scrapling → résultat propre.

**System prompt MANA skill KAZI/KAITO** (section tools) :

```
Tu as accès au MCP Scrapling. Quand l'utilisateur demande d'extraire des données
d'un site web, utilise scrapling_fetch avec les paramètres appropriés.
Retourne uniquement les données structurées, jamais le HTML brut.
```

**server.json sur Elysium VPS** :

```json
{
  "mcpServers": {
    "scrapling": {
      "command": "python",
      "args": ["-m", "scrapling.mcp"],
      "env": {
        "SCRAPLING_DEFAULT_STEALTH": "true",
        "SCRAPLING_BLOCK_ADS": "true"
      }
    }
  }
}
```

---

## 5. Async batch (haute volumétrie) + export Neon

```python
import asyncio
from scrapling.fetchers import AsyncFetcher
import asyncpg

async def batch_scrape_and_store(urls: list[str], selector: str, neon_dsn: str):
    conn = await asyncpg.connect(neon_dsn)

    async def scrape_one(url: str):
        try:
            page  = await AsyncFetcher.get(url, block_ads=True)
            items = page.css(selector, auto_save=True)
            return [(url, el.text, el.attrib.get("href","")) for el in items]
        except Exception as e:
            print(f"[ERR] {url}: {e}")
            return []

    results = await asyncio.gather(*[scrape_one(u) for u in urls])
    flat    = [row for batch in results for row in batch]

    await conn.executemany(
        "INSERT INTO scraped_data (url, text, href, scraped_at) "
        "VALUES ($1, $2, $3, NOW()) ON CONFLICT DO NOTHING",
        flat
    )
    await conn.close()
    print(f"Stored {len(flat)} rows")
```

---

## 6. Migration BS4 → Scrapling (cheat sheet)

| BeautifulSoup4 | Scrapling |
|----------------|-----------|
| `soup.find_all('div', class_='x')` | `page.find_all('div', class_='x')` |
| `soup.find('h2').text` | `page.css('h2::text').get()` |
| `el.get('href')` | `el.attrib['href']` ou `page.css('a::attr(href)').get()` |
| `el.parent` | `el.parent` |
| `el.find_next_sibling()` | `el.next_sibling` |
| `requests.get(url)` + BS4 | `Fetcher.get(url)` (tout en un) |
| Aucun anti-bot | `StealthyFetcher.fetch(url)` |
| Aucun self-healing | `page.css('.x', adaptive=True)` |
