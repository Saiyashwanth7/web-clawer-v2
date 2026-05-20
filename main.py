import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uuid
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
from database import get_db, engine, Base,AsyncSessionLocal
from models import CrawlJob, CrawledPage, ExtractedImage
from schemas import CrawlRequest, CrawlJobResponse
from crawler import crawl


async def background_crawling(job_id:str,url:str,db:AsyncSession):
    async with AsyncSessionLocal() as db:
        await crawl(job_id,url,db)
        
@asynccontextmanager
async def lifespan(app: FastAPI):

    # Startup code
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield


app = FastAPI(lifespan=lifespan)
@app.get("/")
async def home():
    return {"message": "Hello"}

@app.post("/crawl", response_model=CrawlJobResponse)
async def start_crawl(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    job_id = str(uuid.uuid4())[:8]
    job = CrawlJob(id=job_id, seed_url=str(request.url))
    db.add(job)
    await db.commit()

    background_tasks.add_task(background_crawling, job_id, str(request.url), db)

    return CrawlJobResponse(
        job_id=job_id,
        status="started",
        pages_crawled=0,
        images_found=0,
        seed_url=str(request.url),
        created_at=job.created_at
    )

@app.get("/crawl/{job_id}", response_model=CrawlJobResponse)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(CrawlJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return CrawlJobResponse(
        job_id=job.id,
        status=job.status,
        pages_crawled=job.pages_crawled,
        images_found=job.images_found,
        seed_url=job.seed_url,
        created_at=job.created_at
    )

@app.get("/results/{job_id}")
async def get_results(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CrawledPage).where(CrawledPage.job_id == job_id)
    )
    pages = result.scalars().all()
    return {
        "job_id": job_id,
        "pages": [{"url": p.url, "status": p.status_code, "method": p.fetch_method} for p in pages]
    }

@app.get("/images/{job_id}")
async def get_images(job_id: str, logo_only: bool = False, db: AsyncSession = Depends(get_db)):
    query = select(ExtractedImage, CrawledPage.url).join(CrawledPage).where(CrawledPage.job_id == job_id)
    if logo_only:
        query = query.where(ExtractedImage.is_logo == True)
    result = await db.execute(query)
    rows = result.all()
    return {
        "images": [
            {"image_url": img.image_url, "alt": img.alt_text, "is_logo": img.is_logo, "found_on": page_url}
            for img, page_url in rows
        ]
    }