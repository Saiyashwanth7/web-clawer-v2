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
- Fully containerized — published on Docker Hub

---

## Project Structure

```
web-crawler-v2/
├── main.py          # FastAPI app, endpoints, background task runner
├── crawler.py       # BFS crawl logic, aiohttp + Playwright fetchers
├── extractors.py    # extract_links() and extract_images()
├── robots.py        # Async RobotsCache — fetches and caches robots.txt per domain
├── models.py        # SQLAlchemy models — CrawlJob, CrawledPage, ExtractedImage
├── schemas.py       # Pydantic request/response schemas
├── database.py      # Async SQLAlchemy engine and session factory
├── config.py        # Pydantic settings loaded from .env
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env             # Environment variables (not committed)
└── .env.docker      # Docker Environment variables (not committed)
```

---

## Running the Project

There are two ways to run this project. **Docker is strongly recommended**, especially on Windows.

---

### Option 1 — Docker (Recommended)

**Why Docker?**

Playwright launches Chromium as a subprocess. On Windows, Python's default asyncio event loop (`ProactorEventLoop`) does not support spawning subprocesses from within an async context — causing Playwright to crash with `NotImplementedError`. Inside a Docker container, the app runs on Linux where this limitation does not exist. Docker is therefore the only reliable way to run the full dual-fetch strategy (aiohttp + Playwright) on Windows.

#### Step 1 — Pull from Docker Hub

```bash
docker pull saiyashwanthdasari7/mini-web-crawler:latest
```

#### Step 2 — Create `.env.docker`

Create a `.env.docker` file in your project root:

```env
DATABASE_URL=postgresql://postgres:your_password@db:5432/MiniWebCrawler
MAX_CONCURRENT_REQUESTS=10
MAX_PAGES=50
REQUEST_TIMEOUT=10
```

> Note: the host is `db`, not `localhost` — inside Docker, `db` is the service name of the PostgreSQL container resolved automatically by Docker's internal DNS.

#### Step 3 — Create `docker-compose.yml`

```yaml
version: "3.9"

services:
  app:
    image: saiyashwanthdasari7/mini-web-crawler:latest
    ports:
      - "8000:8000"
    env_file:
      - .env.docker
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: your_password
      POSTGRES_DB: MiniWebCrawler
    ports:
      - "5433:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pg_data:
```

> Port `5433` is used externally to avoid conflicts with any local PostgreSQL already running on `5432`. Inside Docker, the app still communicates with the database on `5432` via the `db` service name.

#### Step 4 — Start everything

```bash
docker-compose up
```

Visit `http://localhost:8000/docs` for the interactive API UI.

---

### Option 2 — Run Locally (Mac/Linux only)

> **Windows users:** Playwright will not work locally due to the asyncio event loop limitation described above. Use Docker instead.

#### Step 1 — Clone the repository

```bash
git clone https://github.com/Saiyashwanth7/web-clawer-v2.git
cd web-crawler-v2
```

#### Step 2 — Create virtual environment

```bash
python -m venv venv
source venv/bin/activate      # Mac/Linux
```

#### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

#### Step 4 — Configure environment

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://your_user:your_password@localhost:5432/your_db
MAX_CONCURRENT_REQUESTS=10
MAX_PAGES=50
REQUEST_TIMEOUT=10
```

#### Step 5 — Run the server

```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` for the interactive API UI.

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
  "respect_robots": true,
  "force_recrawl": false
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

> If the same URL was crawled before, the existing job is returned immediately without re-crawling. Set `force_recrawl: true` to start a fresh crawl regardless.

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

The crawler uses BFS (Breadth-First Search) — the same graph traversal algorithm used in production crawlers. Each URL is a node, each link is an edge. URLs are marked as visited at enqueue time to prevent duplicates.

```
seed_url added to queue + visited
         ↓
pop URL from queue
         ↓
check robots.txt → blocked? skip
         ↓
fetch with aiohttp (fast)
         ↓
JS-heavy? (empty visible text) → fallback to Playwright
         ↓
extract links + images
         ↓
save page + images to PostgreSQL
         ↓
add new unvisited links to queue
         ↓
repeat until queue empty or max_pages hit
```

### Fetch Strategy

| Method | Use case | Speed |
|---|---|---|
| aiohttp | Static HTML sites | Fast |
| Playwright | JS-rendered sites | Slower but complete |

JS detection works by stripping `<script>` and `<style>` tags and checking if the remaining visible text is under 200 characters — not by checking raw HTML length, which would miss JS shells with large but empty markup.

### Logo Detection

Images are flagged as logos using structural and keyword heuristics — checking for "logo" or "brand" in `alt` text, CSS class, element ID, and image URL; whether the image is inside a `<header>` or `<nav>`; whether it links back to the homepage; and whether its dimensions match typical logo proportions (wide and short, under 150px tall).

### robots.txt

Every domain's `robots.txt` is fetched once asynchronously and cached in memory for the duration of the crawl. URLs disallowed by `robots.txt` are skipped automatically.

### Duplicate Detection

Before starting a new crawl, the API checks if the same seed URL was crawled before and returns the existing job immediately. Set `force_recrawl: true` in the request body to bypass this and start fresh.

---

## Database Schema

```
crawl_job
  id (String/UUID), seed_url (unique), status, pages_crawled,
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
- **Docker + Docker Compose** — containerization and orchestration

---

## Good Sites to Test

| Site | Why |
|---|---|
| `https://books.toscrape.com` | Static, crawler-friendly, rich content |
| `https://quotes.toscrape.com` | Static version |
| `https://quotes.toscrape.com/js` | JS-rendered — tests Playwright fallback |
| `https://news.ycombinator.com` | Allows crawling, clean HTML |

---

## Future Enhancements

### Logo Detection via ML Classifier
Current logo detection uses heuristics (keyword matching in alt text, class names, URLs, and structural position). A more accurate approach would be a fine-tuned MobileNetV3 image classifier trained on a labeled logo dataset, capable of classifying thousands of images per second on CPU — the approach used in production crawlers operating at scale.

### Async Concurrent Crawling
Currently crawls pages sequentially within the BFS loop. A future version could use `asyncio.gather()` to crawl multiple pages simultaneously, significantly improving throughput on large sites.

### Crawl Depth Control
Add a `max_depth` parameter to limit how many link-hops away from the seed URL the crawler will go, giving users finer control over crawl scope.

### Robots.txt Crawl-Delay Respect
Currently uses a fixed polite delay. A future version could read the `Crawl-Delay` directive from `robots.txt` and respect per-domain rate limits automatically.

### Export to CSV/JSON
Add endpoints to download crawl results as CSV or JSON files directly from the API.