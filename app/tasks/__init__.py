# app/tasks/__init__.py
from app.tasks.celery_tasks import collect_all_rss_feeds, collect_single_rss_feed, cleanup_old_entries

__all__ = ['collect_all_rss_feeds', 'collect_single_rss_feed', 'cleanup_old_entries']