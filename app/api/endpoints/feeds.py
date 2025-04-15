from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
from datetime import datetime

from app.models.database import get_db
from app.models.models import RssFeed
from app.tasks.celery_tasks import collect_single_rss_feed

router = APIRouter()


# Shēmas
class RssFeedBase(BaseModel):
    url: HttpUrl
    name: Optional[str] = None
    active: bool = True


class RssFeedCreate(RssFeedBase):
    pass


class RssFeedUpdate(BaseModel):
    url: Optional[HttpUrl] = None
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    site_url: Optional[HttpUrl] = None
    active: Optional[bool] = None


class RssFeedInDB(RssFeedBase):
    id: int
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    site_url: Optional[str] = None
    language: Optional[str] = None
    last_fetched: Optional[datetime] = None
    error_count: int
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[RssFeedInDB])
def read_feeds(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """
    Atgriež visu RSS barotņu sarakstu ar filtrēšanu
    """
    query = db.query(RssFeed)
    
    if active_only:
        query = query.filter(RssFeed.active == True)
    
    feeds = query.offset(skip).limit(limit).all()
    return feeds


@router.post("/", response_model=RssFeedInDB)
def create_feed(
    feed: RssFeedCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Pievieno jaunu RSS barotni
    """
    # Pārbaudām, vai barotne ar šādu URL jau eksistē
    existing_feed = db.query(RssFeed).filter(RssFeed.url == str(feed.url)).first()
    if existing_feed:
        raise HTTPException(status_code=400, detail="RSS barotne ar šādu URL jau eksistē")
    
    # Izveidojam jaunu barotni
    db_feed = RssFeed(
        url=str(feed.url),
        name=str(feed.name),
        active=feed.active
    )
    
    db.add(db_feed)
    db.commit()
    db.refresh(db_feed)
    
    # Palaižam barotnes ievākšanu fonā
    background_tasks.add_task(collect_single_rss_feed.delay, db_feed.id)
    
    return db_feed


@router.get("/{feed_id}", response_model=RssFeedInDB)
def read_feed(feed_id: int, db: Session = Depends(get_db)):
    """
    Atgriež konkrētas RSS barotnes informāciju
    """
    feed = db.query(RssFeed).filter(RssFeed.id == feed_id).first()
    if feed is None:
        raise HTTPException(status_code=404, detail="RSS barotne nav atrasta")
    return feed


@router.put("/{feed_id}", response_model=RssFeedInDB)
def update_feed(
    feed_id: int,
    feed_update: RssFeedUpdate,
    db: Session = Depends(get_db)
):
    """
    Atjaunina RSS barotnes informāciju
    """
    db_feed = db.query(RssFeed).filter(RssFeed.id == feed_id).first()
    if db_feed is None:
        raise HTTPException(status_code=404, detail="RSS barotne nav atrasta")
    
    # Atjauninām tikai norādītos laukus
    update_data = feed_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_feed, key, value)
    
    db.commit()
    db.refresh(db_feed)
    return db_feed


@router.delete("/{feed_id}", status_code=204)
def delete_feed(feed_id: int, db: Session = Depends(get_db)):
    """
    Dzēš RSS barotni
    """
    db_feed = db.query(RssFeed).filter(RssFeed.id == feed_id).first()
    if db_feed is None:
        raise HTTPException(status_code=404, detail="RSS barotne nav atrasta")
    
    db.delete(db_feed)
    db.commit()
    return None


@router.post("/{feed_id}/fetch", status_code=202)
def fetch_feed(feed_id: int, db: Session = Depends(get_db)):
    """
    Manuāli izsauc RSS barotnes ievākšanu
    """
    feed = db.query(RssFeed).filter(RssFeed.id == feed_id).first()
    if feed is None:
        raise HTTPException(status_code=404, detail="RSS barotne nav atrasta")
    
    # Palaižam ievākšanas uzdevumu Celery
    task = collect_single_rss_feed.delay(feed_id)
    
    return {"task_id": task.id, "status": "accepted"}