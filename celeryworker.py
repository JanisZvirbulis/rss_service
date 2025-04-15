import os
from celery import Celery

# Iestatām vides mainīgos
os.environ.setdefault('PYTHONPATH', '.')

# Importējam uzdevumus tieši
from app.tasks.celery_tasks import collect_all_rss_feeds, collect_single_rss_feed, cleanup_old_entries

# Izveidojam Celery instanci
celery = Celery("rss_service")

# Ielādējam konfigurāciju
celery.config_from_object("celeryconfig")

# Reģistrējam uzdevumus manuāli
celery.task(collect_all_rss_feeds)
celery.task(collect_single_rss_feed)
celery.task(cleanup_old_entries)

if __name__ == '__main__':
    celery.start()