from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Table, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
import uuid

from app.models.database import Base

# Asociācijas tabula "daudzi ar daudziem" starp ierakstiem un tagiem
entry_tag = Table(
    "entry_tag",
    Base.metadata,
    Column("entry_id", String, ForeignKey("entries.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class RssFeed(Base):
    """RSS barotnes modelis"""
    __tablename__ = "rss_feeds"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=True)
    url = Column(String(255), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    site_url = Column(String(255), nullable=True)
    language = Column(String(10), nullable=True)
    last_fetched = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relācijas
    entries = relationship("Entry", back_populates="feed", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<RssFeed {self.title} ({self.url})>"


class Entry(Base):
    """RSS ieraksta modelis"""
    __tablename__ = "entries"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    feed_id = Column(Integer, ForeignKey("rss_feeds.id"), nullable=False)
    title = Column(String(255), nullable=False)
    link = Column(String(512), nullable=False, index=True)
    published = Column(DateTime, nullable=True, index=True)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    original_id = Column(String(512), nullable=True)
    entry_metadata = Column(JSONB, nullable=True)  # Papildu dati JSON formātā
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relācijas
    feed = relationship("RssFeed", back_populates="entries")
    tags = relationship("Tag", secondary=entry_tag, back_populates="entries")
    
    def __repr__(self):
        return f"<Entry {self.title}>"


class Tag(Base):
    """Tagu modelis"""
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relācijas
    entries = relationship("Entry", secondary=entry_tag, back_populates="tags")
    
    def __repr__(self):
        return f"<Tag {self.name}>"