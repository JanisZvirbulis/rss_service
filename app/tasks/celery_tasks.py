from celery import shared_task
import logging
import requests
from bs4 import BeautifulSoup
from readability import Document
from datetime import datetime
from app.models.database import SessionLocal
from app.services.rss_collector import RssCollector
from app.models.models import RssFeed, Entry

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

def get_clean_article_text(url: str) -> str:
    """
    Funkcija, kas iegūst tīru raksta tekstu no news URL
    """
    try:
        # iegustam HTML
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Pārbaudām, vai pieprasījums bija veiksmīgs   

        #readability, lai iegutu raksta galveno tekstu
        doc = Document(response.text)
        article_html = doc.summary()

        #BeautifulSoup, lai iegutu tīru tekstu
        soup = BeautifulSoup(article_html, 'html.parser')
        
        # nonemam nevelabos elementus
        for unwwanted in soup.find_all(['script', 'style', 'iframe', 'noscript', 'aside']):
            unwwanted.decompose()

        # nonemam ari klases vai id
        for unwated in soup.find_all(
            class_=lambda x: x and ('ads' in x or 'piano' in x or 'sidebar' in x)
        ):
            unwated.decompose()

        # iegustam tiru tekstu
        clean_text = soup.get_text(separator='\n\n')

        clean_text = '\n'.join([line.strip() for line in clean_text.split('\n') if line.strip()])
        
        return clean_text
    except Exception as e:
        logger.error(f"Kļūda iegūstot tīru raksta tekstu no URL {url}: {str(e)}")
        return f"kļūda iegūstot tīru raksta tekstu no URL {url}: {str(e)}"

@shared_task(name="fetch_full_article_content")  
def fetch_full_article_content(entry_id: str) -> str:
    """
    Celery uzdevums, kas iegūst pilnu raksta saturu no ievadītā ID
    """
    db = SessionLocal()
    try:
        logger.info(f"Sākas pilna raksta satura iegūšana no ievadītā ID {entry_id}")
        # Iegūstam ierakstu no datubāzes   
        entry = db.query(Entry).filter(Entry.id == entry_id).first()
        if not entry:
            logger.error(f"Ieraksts ar ID {entry_id} nav atrasts")
            return {"error": "Entry not found"}
        
        # Iegūstam tīru raksta tekstu no URL
        clean_text = get_clean_article_text(entry.link)

        if clean_text and not clean_text.startswith("kļūda"):
            # Atjaunojam ieraksta saturu datubāzē
            entry.content = clean_text
            entry.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Veiksmīgi iegūts pilns raksta saturs no {entry.link}")
            return {"success": True, }
        else:
            logger.error(f"Kļūda iegūstot pilnu raksta saturu no {entry.link}")
            return {"success": False, }
    except Exception as e:
        db.rollback()
        logger.error(f"Kļūda iegūstot pilnu raksta saturu no ievadītā ID {entry_id}: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()

    