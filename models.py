from sqlalchemy import Column,Text,Boolean,Integer,String,DateTime,ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime,timezone,timedelta
from database import Base

# We will use 3 tables for this mini-crawler. One to store the progress of the current crawl (CrawlJob), second one to store all extracted images of a page (ExtractedImages), and the last one to store the pages we crawled(CrawledPage).

# crawled_pages.images is in one to many relation with extracted_images.page

class CrawledPage(Base):
    __tablename__="crawled_pages"
    id = Column(Integer,primary_key=True)
    job_id = Column(String,index=True)
    domain_name = Column(String,index=True)
    url = Column(String,unique=True,index=True)
    html_content = Column(Text)
    status_code = Column(Integer)
    fetch_method = Column(String,default="aiohttp") # one of two methods aiohttp or palywright
    crawled_at = Column(DateTime(timezone=True),default=datetime.now(timezone.utc))
    images = relationship("ExtractedImage",back_populates="page")
    
class ExtractedImage(Base):
    __tablename__="extracted_images"
    id = Column(Integer,primary_key=True)
    page_id = Column(Integer,ForeignKey("crawled_pages.id"))
    image_url = Column(String)
    alt_text = Column(String)
    is_logo = Column(Boolean,default=False)
    extracted_at = Column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc))
    page = relationship("CrawledPage",back_populates="images")

class CrawlJob(Base):
    __tablename__="crawl_job"
    id = Column(String,primary_key=True) #we use UUID here
    seed_url = Column(String)
    status = Column(String,default="pending") #pending,running,completed,failed
    pages_crawled = Column(Integer,default=0)
    images_found = Column(Integer,default=0)
    created_at = Column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True),nullable=True)

