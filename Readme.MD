# MiniWebCrawler

A production-grade async web crawler built with FastAPI and PostgreSQL. Accepts any seed URL, crawls up to 50 pages using BFS, extracts images with logo detection, and persists everything to a database. Automatically falls back to Playwright for JavaScript-heavy sites.

---

## Features

- Async BFS crawling with configurable page limits
- Dual fetch strategy — aiohttp first, Playwright fallback for JS-heavy sites
- robots.txt compliance with per-domain async caching
- Image extraction with logo detection heuristics
- PostgreSQL persistence for jobs, pages, and images
- REST API with background job tracking

---

## Project Structure

```
web-clawer-v2/
├── main.py          # FastAPI app, endpoints, background task runner
├── crawler.py       # BFS crawl logic, aiohttp + Playwright fetchers
├── extractors.py    # extract_links() and extract_images()
├── robots.py        # Async RobotsCache — fetches and caches robots.txt per domain
├── models.py        # SQLAlchemy models — CrawlJob, CrawledPage, ExtractedImage
├── schemas.py       # Pydantic request/response schemas
├── database.py      # Async SQLAlchemy engine and session factory
├── config.py        # Pydantic settings loaded from .env
├── requirements.txt
└── .env             # Environment variables (not committed)
```

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/Saiyashwanth7/web-clawer-v2.git
cd web-crawler-v2
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure environment

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://your_user:your_password@localhost:5432/your_db
```

### 4. Run the server

```bash
uvicorn main:app --reload --loop asyncio
```

> `--loop asyncio` is required on Windows for Playwright subprocess support.

---

## API Endpoints

### Start a crawl

```
POST /crawl
```

Request body:
```json
{
  "url": "https://books.toscrape.com/",
  "max_pages": 50,
  "use_playwright": true,
  "respect_robots": true
}
```

Response:
```json
{
  "job_id": "656a9196", 
  "status": "started",
  "pages_crawled": 0,
  "images_found": 0,
  "seed_url": "https://books.toscrape.com/",
  "created_at": "2026-05-20T15:52:54.090728Z"
}
```

---

### Check job status

```
GET /crawl/{job_id}
```

Response:
```json
{
  "job_id": "656a9196",
  "status": "completed",
  "pages_crawled": 50,
  "images_found": 498,
  "seed_url": "https://books.toscrape.com/",
  "created_at": "2026-05-20T15:52:54.090728Z"
}
```

Job status values: `pending` → `running` → `completed` / `failed`

---

### Get crawled pages

```
GET /results/{job_id}
```

Response:
```json
{
  "job_id": "656a9196",
  "pages": [
    {"url": "https://books.toscrape.com/", "status": 200, "method": "aiohttp"},
    {"url": "https://books.toscrape.com/catalogue/page-2.html", "status": 200, "method": "aiohttp"}
  ]
}
```

---

### Get extracted images

```
GET /images/{job_id}
GET /images/{job_id}?logo_only=true
```

Response:
```json
{
  "images": [
    {
      "image_url": "https://books.toscrape.com/media/cache/logo.png",
      "alt": "Books to Scrape",
      "is_logo": true,
      "found_on": "https://books.toscrape.com/"
    }
  ]
}
```

---

## How It Works

### Crawling Strategy

The crawler uses BFS (Breadth-First Search) — the same graph traversal algorithm used in production crawlers. Each URL is a node, each link is an edge.

```
seed_url added to queue + visited
         ↓
pop URL from queue
         ↓
check robots.txt → blocked? skip
         ↓
fetch with aiohttp (fast)
         ↓
JS-heavy? (empty content) → fallback to Playwright
         ↓
extract links + images
         ↓
save page + images to PostgreSQL
         ↓
add new links to queue
         ↓
repeat until queue empty or max_pages hit
```

### Fetch Strategy

| Method | Use case | Speed |
|---|---|---|
| aiohttp | Static HTML sites | Fast |
| Playwright | JS-rendered sites | Slower but complete |

### Logo Detection

Images are flagged as logos using heuristics — checking for the word "logo" or "brand" in the `alt` text, CSS class, element ID, image URL, and whether the image lives inside a `<header>` or `<nav>` tag.

### robots.txt

Every domain's `robots.txt` is fetched once and cached in memory for the duration of the crawl. URLs disallowed by `robots.txt` are skipped automatically.

---

## Database Schema

```
crawl_job
  id (String/UUID), seed_url, status, pages_crawled,
  images_found, created_at, completed_at

crawled_pages
  id, job_id → crawl_job, url (unique), html_content,
  status_code, fetch_method, crawled_at

extracted_images
  id, page_id → crawled_pages, image_url, alt_text,
  is_logo, extracted_at
```

---

## Tech Stack

- **FastAPI** — async REST API framework
- **SQLAlchemy (async)** + **asyncpg** — async PostgreSQL ORM
- **aiohttp** — async HTTP client for fast page fetching
- **Playwright** — headless Chromium for JS-heavy sites
- **BeautifulSoup4** — HTML parsing
- **Pydantic** — settings and schema validation
- **PostgreSQL** — persistent storage

---

## Good Sites to Test

| Site | Why |
|---|---|
| `https://books.toscrape.com` | Static, crawler-friendly, rich content |
| `https://quotes.toscrape.com` | Static version |
| `https://quotes.toscrape.com/js` | JS-rendered — tests Playwright fallback |
| `https://news.ycombinator.com` | Allows crawling, clean HTML |