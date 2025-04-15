from celery import shared_task
import logging
from app.models.database import SessionLocal
from app.services.rss_collector import RssCollector
from app.models.models import RssFeed

# Konfigurējam žurnalēšanu
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@shared_task(name="collect_all_rss_feeds")
def collect_all_rss_feeds():
    """
    Celery uzdevums, kas ievāc datus no visām aktīvajām RSS barotnēm
    """
    logger.info("Sākas periodiskais RSS ievākšanas process")
    db = SessionLocal()
    
    try:
        # Iegūstam visas aktīvās barotnes
        active_feeds = db.query(RssFeed).filter(RssFeed.active == True).all()
        
        # Rezultātu statistika
        results = {
            "success": 0,
            "error": 0,
            "new_entries": 0
        }
        
        logger.info(f"Sākam ievākt datus no {len(active_feeds)} aktīvajām RSS barotnēm")
        
        # Apstrādājam katru barotni secīgi (bez vienlaicīguma)
        for feed in active_feeds:
            try:
                # Izveidojam jaunu sesiju katrai barotnei
                feed_db = SessionLocal()
                collector = RssCollector(feed_db)
                
                # Iegūstam barotni no datubāzes
                feed_fresh = feed_db.query(RssFeed).filter(RssFeed.id == feed.id).first()
                
                if feed_fresh:
                    success, entry_count = collector.fetch_single_feed(feed_fresh)
                    if success:
                        results["success"] += 1
                        results["new_entries"] += entry_count
                    else:
                        results["error"] += 1
                
                feed_db.close()
            except Exception as e:
                logger.error(f"Kļūda apstrādājot barotni {feed.url}: {str(e)}")
                results["error"] += 1
        
        logger.info(f"RSS ievākšana pabeigta. Veiksmīgi: {results['success']}, "
                  f"Kļūdas: {results['error']}, Jauni ieraksti: {results['new_entries']}")
        
        return results
    except Exception as e:
        logger.error(f"Kļūda periodiskajā RSS ievākšanas procesā: {str(e)}")
        raise
    finally:
        db.close()


@shared_task(name="collect_single_rss_feed")
def collect_single_rss_feed(feed_id: int):
    """
    Celery uzdevums, kas ievāc datus no konkrētas RSS barotnes
    """
    logger.info(f"Sākas RSS ievākšana barotnei ar ID {feed_id}")
    db = SessionLocal()
    
    try:
        # Iegūstam barotni no datubāzes
        feed = db.query(RssFeed).filter(RssFeed.id == feed_id).first()
        
        if not feed:
            logger.error(f"Barotne ar ID {feed_id} nav atrasta")
            return {"error": "Feed not found"}
        
        # Ievācam datus
        collector = RssCollector(db)
        success, entry_count = collector.fetch_single_feed(feed)
        
        if success:
            logger.info(f"Veiksmīgi ievākti dati no barotnes {feed.url}. Pievienoti {entry_count} jauni ieraksti.")
            return {"success": True, "new_entries": entry_count}
        else:
            logger.error(f"Kļūda ievācot datus no barotnes {feed.url}")
            return {"success": False, "error": feed.last_error}
    except Exception as e:
        logger.error(f"Kļūda ievācot datus no barotnes ar ID {feed_id}: {str(e)}")
        raise
    finally:
        db.close()


@shared_task(name="cleanup_old_entries")
def cleanup_old_entries(days: int = 30):
    """
    Celery uzdevums, kas attīra vecos ierakstus, kas vecāki par norādīto dienu skaitu
    """
    from datetime import datetime, timedelta
    from app.models.models import Entry
    
    logger.info(f"Sākas veco ierakstu attīrīšana (vecāki par {days} dienām)")
    db = SessionLocal()
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = db.query(Entry).filter(Entry.published < cutoff_date).delete()
        db.commit()
        
        logger.info(f"Dzēsti {deleted_count} veci ieraksti")
        return {"deleted_count": deleted_count}
    except Exception as e:
        db.rollback()
        logger.error(f"Kļūda dzēšot vecos ierakstus: {str(e)}")
        raise
    finally:
        db.close()