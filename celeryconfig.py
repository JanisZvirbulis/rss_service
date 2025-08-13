from celery.schedules import crontab
from app.config import settings

# Celery brokera un rezultātu datubāzes adreses
broker_url = settings.CELERY_BROKER_URL
result_backend = settings.CELERY_RESULT_BACKEND

# Uzdevumu maršruti
task_routes = {
    'collect_all_rss_feeds': {'queue': 'feeds'},
    'collect_single_rss_feed': {'queue': 'feeds'},
    'cleanup_old_entries': {'queue': 'maintenance'},
    'fetch_full_article_content': {'queue': 'content'},
}

# Darbu izsaukšanas grafiks
beat_schedule = {
    'collect-all-feeds-every-five-min': {
        'task': 'collect_all_rss_feeds',
        #'schedule': crontab(minute=0, hour='*/1'),  # Katru stundu
        'schedule': crontab(minute='*/5'),  # Katras 5 min
    },
    'cleanup-old-entries-daily': {
        'task': 'cleanup_old_entries',
        'schedule': crontab(minute=0, hour=3),  # Katru dienu plkst. 3:00
        'kwargs': {'days': 30},  # Parametri uzdevumam
    },
}

# Celery darbinieku konfigurācija
worker_concurrency = 2 # Vienlaicīgo procesu skaits
worker_max_tasks_per_child = 1000  # Pārstartē darbinieku pēc 1000 uzdevumiem

# Celery monitoringa konfigurācija - Flower
flower_basic_auth = None  # Piemērs: ['admin:password']

# Darba izpildes opcijas
task_acks_late = True  # Apstiprina uzdevumu tikai pēc tā veiksmīgas izpildes
task_reject_on_worker_lost = True  # Atgriež uzdevumu rindā, ja darbinieks avariski beidz darbu

# Uzdevumu noilgums (timeout) sekundēs
task_time_limit = 600  # 10 minūtes
task_soft_time_limit = 480  # 8 minūtes