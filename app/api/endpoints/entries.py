from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import desc, and_

from app.tasks.celery_tasks import fetch_full_article_content
from app.models.database import get_db
from app.models.models import Entry, RssFeed, Tag, entry_tag

router = APIRouter()


# Shēmas
class TagResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class EntryBase(BaseModel):
    title: str
    link: str
    published: Optional[datetime] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None


class EntryInDB(EntryBase):
    id: str
    feed_id: int
    feed_title: Optional[str] = None
    created_at: datetime
    tags: List[TagResponse] = []

    class Config:
        from_attributes = True


class StatusMessage(BaseModel):
    status: str
    message: str


@router.get("/", response_model=List[EntryInDB])
def read_entries(
    skip: int = 0,
    limit: int = 20,
    feed_id: Optional[int] = None,
    search: Optional[str] = None,
    tag: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    sort_by: str = "published",
    sort_desc: bool = True,
    db: Session = Depends(get_db),
):
    """
    Atgriež RSS ierakstu sarakstu ar filtrēšanu un meklēšanu
    """
    # Veidojam bāzes vaicājumu ar pievienoto barotnes nosaukumu
    query = db.query(Entry, RssFeed.title.label("feed_title")).join(
        RssFeed, Entry.feed_id == RssFeed.id
    )

    # Pievienojam filtrus
    filters = []

    if feed_id:
        filters.append(Entry.feed_id == feed_id)

    if search:
        search_term = f"%{search}%"
        filters.append(
            (
                Entry.title.ilike(search_term)
                | Entry.summary.ilike(search_term)
                | Entry.content.ilike(search_term)
            )
        )

    if tag:
        query = query.join(Entry.tags).filter(Tag.name == tag)

    if from_date:
        filters.append(Entry.published >= from_date)

    if to_date:
        filters.append(Entry.published <= to_date)

    if filters:
        query = query.filter(and_(*filters))

    # Šķirošana
    if sort_by == "published":
        order_col = Entry.published
    elif sort_by == "created":
        order_col = Entry.created_at
    else:
        order_col = Entry.published  # Noklusējuma šķirošana

    if sort_desc:
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(order_col)

    # Limitējam rezultātus
    results = query.offset(skip).limit(limit).all()

    # Veidojam atbildi
    entries = []
    for entry, feed_title in results:
        # Iegūstam Entry objektu ar papildu feed_title lauku
        entry_dict = {
            "id": entry.id,
            "feed_id": entry.feed_id,
            "feed_title": feed_title,
            "title": entry.title,
            "link": entry.link,
            "published": entry.published,
            "summary": entry.summary,
            "content": entry.content,
            "author": entry.author,
            "created_at": entry.created_at,
            "tags": entry.tags,
        }
        entries.append(EntryInDB(**entry_dict))

    return entries


@router.get("/{entry_id}", response_model=EntryInDB)
def read_entry(entry_id: str, db: Session = Depends(get_db)):
    """
    Atgriež konkrēta RSS ieraksta informāciju
    """
    entry = db.query(Entry).filter(Entry.id == entry_id).first()

    if entry is None:
        raise HTTPException(status_code=404, detail="Ieraksts nav atrasts")

    # Iegūstam barotnes nosaukumu
    feed = db.query(RssFeed).filter(RssFeed.id == entry.feed_id).first()
    feed_title = feed.title if feed else None

    # Pievienojam feed_title atbildei
    entry_dict = {
        "id": entry.id,
        "feed_id": entry.feed_id,
        "feed_title": feed_title,
        "title": entry.title,
        "link": entry.link,
        "published": entry.published,
        "summary": entry.summary,
        "content": entry.content,
        "author": entry.author,
        "created_at": entry.created_at,
        "tags": entry.tags,
    }

    return EntryInDB(**entry_dict)


@router.post("/{entry_id}/fetch-content", response_model=StatusMessage)
def fetch_entry_content(
    entry_id: str,
    db: Session = Depends(get_db),
):
    """
    Manuāli iegūst pilno raksta tekstu
    """
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Ieraksts nav atrasts")

    # Izsaucam uzdevumu
    fetch_full_article_content.delay(entry_id)

    return StatusMessage(status="success", message="Pilnā raksta iegūšana uzsākta")


@router.get("/tags/", response_model=List[TagResponse])
def read_tags(limit: int = 50, db: Session = Depends(get_db)):
    """
    Atgriež visus pieejamos tagus
    """
    tags = db.query(Tag).limit(limit).all()
    return tags


@router.get("/stats/sources", response_model=dict)
def get_sources_stats(db: Session = Depends(get_db)):
    """
    Atgriež statistiku par ziņu avotiem
    """
    # Importējam sqlalchemy funkcijas
    from sqlalchemy import func

    # Iegūstam kopējo ierakstu skaitu katrai barotnei
    results = (
        db.query(
            RssFeed.id,
            RssFeed.title,
            RssFeed.url,
            func.count(Entry.id).label("entry_count"),
        )
        .outerjoin(Entry, RssFeed.id == Entry.feed_id)
        .group_by(RssFeed.id)
        .order_by(func.count(Entry.id).desc())
        .all()
    )

    stats = {}
    for feed_id, title, url, count in results:
        stats[feed_id] = {"title": title, "url": url, "entry_count": count}

    return stats


@router.delete("/", status_code=200)
def delete_all_entries(
    confirm: bool = Query(False, description="Apstiprināt visas dzēšanas operācijas"),
    db: Session = Depends(get_db),
):
    """
    Dzēš visus RSS ierakstus no datubāzes. Nepieciešams `confirm=true` kā parametrs.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Lai dzēstu visus ierakstus, nepieciešams parametrs 'confirm=true'",
        )

    try:
        # Vispirms jāattīra ieraksti no tagiem (many-to-many saites)
        db.execute("""DELETE FROM entry_tag""")

        # Tad varam dzēst pašus ierakstus
        entries_count = db.query(Entry).delete()
        db.commit()

        return {
            "message": f"Veiksmīgi dzēsti {entries_count} ieraksti",
            "deleted_count": entries_count,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Kļūda dzēšot ierakstus: {str(e)}")


@router.delete("/tags", status_code=200)
def delete_all_tags(
    confirm: bool = Query(False, description="Apstiprināt visas dzēšanas operācijas"),
    db: Session = Depends(get_db),
):
    """
    Dzēš visus tagus, kas nav saistīti ar ierakstiem. Nepieciešams `confirm=true` kā parametrs.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Lai dzēstu visus tagus, nepieciešams parametrs 'confirm=true'",
        )

    try:
        # Izveidojam subquery ar visiem tagiem, kas nav izmantoti
        unused_tags = (
            db.query(Tag.id)
            .outerjoin(entry_tag, Tag.id == entry_tag.c.tag_id)
            .filter(entry_tag.c.entry_id == None)
            .subquery()
        )

        # Dzēšam neizmantotos tagus
        tags_count = (
            db.query(Tag)
            .filter(Tag.id.in_(unused_tags))
            .delete(synchronize_session=False)
        )
        db.commit()

        return {
            "message": f"Veiksmīgi dzēsti {tags_count} neizmantoti tagi",
            "deleted_count": tags_count,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Kļūda dzēšot tagus: {str(e)}")


@router.delete("/tags/all", status_code=200)
def delete_all_tags_with_relations(
    confirm: bool = Query(False, description="Apstiprināt visas dzēšanas operācijas"),
    db: Session = Depends(get_db),
):
    """
    Dzēš visus tagus un to saites ar ierakstiem. Nepieciešams `confirm=true` kā parametrs.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Lai dzēstu visus tagus un saites, nepieciešams parametrs 'confirm=true'",
        )

    try:
        # Vispirms dzēšam saites starp tagiem un ierakstiem
        db.execute("""DELETE FROM entry_tag""")

        # Tad dzēšam pašus tagus
        tags_count = db.query(Tag).delete()
        db.commit()

        return {
            "message": f"Veiksmīgi dzēsti {tags_count} tagi un visas to saistības ar ierakstiem",
            "deleted_count": tags_count,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Kļūda dzēšot tagus un saites: {str(e)}"
        )
