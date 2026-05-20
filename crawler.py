import asyncio
import aiohttp
from collections import deque
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from playwright.async_api import async_playwright
from datetime import datetime, timezone
from models import CrawledPage, ExtractedImage, CrawlJob
from extractors import extract_links, extract_images, is_content_empty
from robots import RobotsCache
from config import settings
from urllib.parse import urlparse

# In this file, we are going to cover 3 functions, 2 of them are for extracting html contents,
# and the other one is the main crawler logic

# first is the fetch_with_playwright(), this is a basic playwright usage, just to extract html content 
# this might take more time than the aiohttp methid because we are using the timeout's 
# pausing for website to fully load.

# second is the fetch_with_aiohttp(), this will use asyncio.ClientSession to get the html content.

#Third one is the final crawling function where all the extractors and fetch methids are used,
# actually this is pretty much of an undirected Graph traversal problem where we use BFS with visited set()
# This only covers limited number of pages(we set max_pages = 50 for the testing).

import asyncio
from playwright.sync_api import sync_playwright

async def fetch_with_playwright(url: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_playwright_fetch, url)

def _sync_playwright_fetch(url: str):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            html = page.content()
            browser.close()
            return html, 200, "playwright"
    except Exception as e:
        print(f"Exception in playwright: {e}")
        return None, None, None

"""async def fetch_with_playwright(url):
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(
                url, timeout=15000
            )  # wait for the website to open completely
            await page.wait_for_load_state("networkidle", timeout=10000)
            html = await page.content()
            await browser.close()
            return html, 200, "playwright"
        except Exception as e:
            print("Exception occured at fetch_with_playwright:", e)
            return None, None, None"""


async def fetch_with_aiohttp(
    url: str, session: aiohttp.ClientSession, sem: asyncio.Semaphore
):
    async with sem:
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=settings.request_timeout),
                headers={"User-Agent":"MiniWebCraweler/1.0"},
            ) as response:
                html = await response.text()
                return html, 200, "aiohttp"

        except Exception as e:
            print("Exception occured at fetch_with_aiohttp:", e)
            return None, None, None


async def crawl(job_id: str, seed_url: str, db: AsyncSession):
    sem = asyncio.Semaphore(settings.max_concurrent_requests)
    robots_cache = RobotsCache()
    q = deque()
    visited = set()
    domain = urlparse(seed_url).netloc
    q.append(seed_url)

    # now, update the job status from "pending" to "running"
    job = await db.get(CrawlJob, job_id)
    job.status = "running"
    await db.commit()

    # Now starts the BFS traversal for each page
    async with aiohttp.ClientSession() as session:
        while q and len(visited) < settings.max_pages:
            url = q.popleft()
            print(f'Crawling....{url}')
            if url in visited:
                continue
            visited.add(url)
            # Before actual
            parser = await robots_cache.get_parser(url, session)
            if not robots_cache.is_allowed(parser, url):
                print(f"Blocked by robots.txt: {url}")
                continue
            html, status, method = await fetch_with_aiohttp(url, session, sem)
            if not html or is_content_empty(html):
                print(f"Switching to playwright for {url}")
                html, status, method = await fetch_with_playwright(url)


            if not html:
                print(f'Skipping the {url}, both fetch methods failed')
                continue
            links = extract_links(html, url)
            images = extract_images(html, url)

            # Now, we have html for the current page, so we can store it in the db
            new_page_record = CrawledPage(
                job_id=job_id,
                domain_name = domain,
                url=url,
                html_content=html,
                status_code=status,
                fetch_method=method,
            )

            db.add(
                new_page_record
            )  # await is not required for adding new records into the db
            await db.flush()
            # we are using the flush method, so we can extract the page id to store it in the extracted_images table

            for img in images:
                db.add(ExtractedImage(page_id=new_page_record.id, **img))

            await db.commit()

            # now again, update the job table columns
            job.images_found += len(images)
            job.pages_crawled = len(visited)
            await db.commit()

            # now, add the extracted new links to the q, just like any graph problem
            for link in links:
                if link not in visited:
                    q.append(link)

        # Now, after the entire website (or max_pages number of pages are crawled),
        # we now update the job status from running to completed
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        print(f"Crawling done for job id:{job_id}, crawling {len(visited)} pages ")
