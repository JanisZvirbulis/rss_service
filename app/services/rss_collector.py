import feedparser
import requests
import datetime
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
import pytz
from bs4 import BeautifulSoup
import concurrent.futures
from datetime import datetime
import traceback
from dateutil import parser

from app.models.models import RssFeed, Entry, Tag
from app.config import settings

# Konfigurējam žurnalēšanu
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RssCollector:
    """
    RSS datu ievākšanas serviss, kas apstrādā RSS barotnes un saglabā datus datubāzē.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.timeout = settings.RSS_REQUEST_TIMEOUT
    
    def fetch_all_feeds(self) -> Dict[str, int]:
        """
        Ievāc datus no visām aktīvajām RSS barotnēm
        """
        # Iegūstam visas aktīvās barotnes
        active_feeds = self.db.query(RssFeed).filter(RssFeed.active == True).all()
        
        # Saglabājam barotņu ID, lai vēlāk varētu izveidot jaunas sesijas katrai pavedieniem
        feed_ids = [feed.id for feed in active_feeds]
        
        logger.info(f"Sākam ievākt datus no {len(active_feeds)} aktīvajām RSS barotnēm")
        
        # Rezultātu statistika
        results = {
            "success": 0,
            "error": 0,
            "new_entries": 0
        }
        
        # Izmantojam konkurējošo izpildi, bet ar atsevišķu sesiju katrai pavedieniem
        with concurrent.futures.ThreadPoolExecutor(max_workers=settings.RSS_CONCURRENT_REQUESTS) as executor:
            future_to_feed_id = {
                executor.submit(self._fetch_feed_with_new_session, feed_id): feed_id
                for feed_id in feed_ids
            }
            
            for future in concurrent.futures.as_completed(future_to_feed_id):
                feed_id = future_to_feed_id[future]
                try:
                    success, entry_count = future.result()
                    if success:
                        results["success"] += 1
                        results["new_entries"] += entry_count
                    else:
                        results["error"] += 1
                except Exception as exc:
                    logger.error(f"Barotnes ar ID {feed_id} apstrāde izraisīja izņēmumu: {exc}")
                    results["error"] += 1
        
        logger.info(f"RSS ievākšana pabeigta. Veiksmīgi: {results['success']}, "
                f"Kļūdas: {results['error']}, Jauni ieraksti: {results['new_entries']}")
        
        return results
    
    def fetch_single_feed(self, feed: RssFeed) -> tuple[bool, int]:
        """
        Ievāc datus no vienas RSS barotnes un saglabā tos datubāzē
        """
        logger.info(f"Ievācam datus no: {feed.url}")
        new_entries_count = 0
        
        try:
            # Mēģinam iegūt RSS barotni
            response = requests.get(feed.url, timeout=self.timeout, verify=True)
            response.raise_for_status()  # Pārbauda, vai atbilde ir veiksmīga
            
            # Parsējam RSS
            parsed_feed = feedparser.parse(response.content)
            
            if parsed_feed.bozo and hasattr(parsed_feed, 'bozo_exception'):
                # Brīdinājums par parsēšanas kļūdām
                logger.warning(f"RSS barotnē {feed.url} ir kļūdas: {parsed_feed.bozo_exception}")
            
            # Atjaunojam barotnes metadatus
            if hasattr(parsed_feed, 'feed'):
                feed.title = parsed_feed.feed.get('title', feed.title)
                feed.description = parsed_feed.feed.get('description', feed.description)
                feed.site_url = parsed_feed.feed.get('link', feed.site_url)
                feed.language = parsed_feed.feed.get('language', feed.language)
            
            # Apstrādājam ierakstus
            for entry in parsed_feed.entries:
                # Pārbaudām, vai ieraksts jau eksistē datubāzē
                original_id = entry.get('id', entry.get('link', ''))
                existing_entry = self.db.query(Entry).filter(
                    (Entry.original_id == original_id) | (Entry.link == entry.get('link', ''))
                ).first()
                
                if existing_entry:
                    continue  # Izlaižam ierakstus, kas jau eksistē
                
                # Apstrādājam publicēšanas datumu
                published = entry.get('published', entry.get('updated', None))
                published_date = None
                
                if published:
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            # Izmantojam parsēto datumu, ja tāds ir
                            date_tuple = entry.published_parsed[0:6]
                            published_date = datetime(*date_tuple)
                        else:
                            # Manuāli mēģinām parsēt datumu
                            
                            published_date = parser.parse(published)
                    except Exception as e:
                        logger.warning(f"Neizdevās parsēt datumu '{published}': {e}")
                        published_date = datetime.utcnow()
                else:
                    published_date = datetime.utcnow()
                
                # Iegūstam saturu
                content = ''
                if 'content' in entry and entry.content:
                    content = entry.content[0].get('value', '')
                elif 'summary_detail' in entry and entry.summary_detail:
                    content = entry.summary_detail.get('value', '')
                elif 'summary' in entry:
                    content = entry.get('summary', '')
                
                # Iztīram HTML
                soup = BeautifulSoup(content, 'lxml')
                clean_content = soup.get_text(separator=' ', strip=True)
                
                soup = BeautifulSoup(entry.get('summary', ''), 'lxml')
                clean_summary = soup.get_text(separator=' ', strip=True)
                
                # Izveidojam jaunu ierakstu
                new_entry = Entry(
                    feed_id=feed.id,
                    title=entry.get('title', ''),
                    link=entry.get('link', ''),
                    published=published_date,
                    summary=clean_summary,
                    content=clean_content,
                    author=entry.get('author', ''),
                    original_id=original_id,
                    metadata=self._prepare_metadata(entry)
                )
                
                # Svarīgi - vispirms pievienojam ierakstu sesijai un saglabājam
                self.db.add(new_entry)
                self.db.flush()  # Ģenerējam ID un saglabājam ierakstu datubāzē

                # Tikai pēc tam apstrādājam tagus
                if 'tags' in entry and entry.tags:
                    for tag_item in entry.tags:
                        tag_name = tag_item.get('term', '')
                        if tag_name:
                            # Pārbaudām, vai tags jau eksistē
                            tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
                            if not tag:
                                tag = Tag(name=tag_name)
                                self.db.add(tag)
                                self.db.flush()  # Iegūstam tag ID
                            
                            # Pārbaudām, vai šis tags jau ir pievienots ierakstam
                            if tag not in new_entry.tags:
                                new_entry.tags.append(tag)

                # Papildu flush, lai saglabātu attiecības
                self.db.flush()
                new_entries_count += 1
            
            # Atjaunojam barotnes statusu
            feed.last_fetched = datetime.utcnow()
            feed.error_count = 0
            feed.last_error = None
            
            # Saglabājam izmaiņas
            self.db.commit()
            logger.info(f"Barotnei {feed.url} pievienoti {new_entries_count} jauni ieraksti")
            return True, new_entries_count
            
        except Exception as e:
            # Apstrādājam kļūdas
            self.db.rollback()
            error_msg = str(e)
            trace = traceback.format_exc()
            logger.error(f"Kļūda apstrādājot barotni {feed.url}: {error_msg}\n{trace}")
            
            # Atjaunojam barotnes kļūdu statusu
            feed.error_count += 1
            feed.last_error = error_msg
            feed.last_fetched = datetime.utcnow()
            
            # Ja sasniegts maksimālais kļūdu skaits, deaktivizējam barotni
            if feed.error_count >= 5:  # Pēc 5 secīgām kļūdām deaktivizējam
                logger.warning(f"Barotne {feed.url} deaktivizēta pēc {feed.error_count} secīgām kļūdām")
                feed.active = False
            
            self.db.commit()
            return False, 0
    
    def _prepare_metadata(self, entry) -> Dict[str, Any]:
        """
        Sagatavo papildu metadatus no ieraksta
        """
        metadata = {}
        
        # Metadati, kurus varam saglabāt
        for key in ['comments', 'guidislink', 'image', 'enclosures']:
            if key in entry:
                metadata[key] = entry.get(key)
        
        # Pārbaudām, vai ir pieejami medija faili
        if 'media_content' in entry:
            metadata['media'] = entry.media_content
        
        # Pārbaudām, vai ir pieejama ģeolokācija
        if 'geo_lat' in entry and 'geo_long' in entry:
            metadata['geo'] = {
                'lat': entry.geo_lat,
                'long': entry.geo_long
            }
        
        return metadata
    
    def _fetch_feed_with_new_session(self, feed_id: int) -> tuple[bool, int]:
        """
        Izveido jaunu sesiju un ievāc datus no konkrētas RSS barotnes
        """
        # Izveidojam jaunu sesiju katrai pavedieniem
        from app.models.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Iegūstam barotni no datubāzes
            feed = db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            
            if not feed:
                logger.error(f"Barotne ar ID {feed_id} nav atrasta")
                return False, 0
            
            # Ievācam datus, izmantojot atsevišķu sesiju
            collector = RssCollector(db)
            result = collector.fetch_single_feed(feed)
            
            # Aizveŗam sesiju
            db.close()
            
            return result
        except Exception as e:
            logger.error(f"Kļūda ievācot datus no barotnes ar ID {feed_id}: {str(e)}")
            db.close()
            return False, 0