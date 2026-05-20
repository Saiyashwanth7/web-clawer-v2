from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 50
    use_playwright: bool = True
    respect_robots: bool = True

class CrawlJobResponse(BaseModel):
    job_id: str
    status: str
    pages_crawled: int
    images_found: int
    seed_url: str
    created_at: datetime

class ImageResult(BaseModel):
    image_url: str
    alt_text: str
    is_logo: bool
    page_url: str