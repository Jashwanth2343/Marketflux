import feedparser
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict
import asyncio
import httpx
from ai_service import analyze_sentiments_batch

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex", "category": "general"},
    {"name": "Google News Business", "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en", "category": "general"},
    {"name": "CNBC Top News", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "category": "general"},
    {"name": "MarketWatch", "url": "https://feeds.marketwatch.com/marketwatch/topstories/", "category": "general"},
    {"name": "CNBC Technology", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910", "category": "technology"},
    {"name": "CNBC Finance", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", "category": "finance"},
    {"name": "CNBC World", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362", "category": "world"},
]


def generate_article_id(title: str, source: str) -> str:
    content = f"{title}:{source}".lower().strip()
    return hashlib.md5(content.encode()).hexdigest()


def parse_date(date_str: str) -> datetime:
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


async def fetch_single_feed(feed_info: Dict) -> List[Dict]:
    articles = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = await client.get(feed_info["url"], headers=headers, follow_redirects=True)
            if response.status_code != 200:
                logger.warning(f"Feed {feed_info['name']} returned {response.status_code}")
                return articles

            feed = feedparser.parse(response.text)

            for entry in feed.entries[:25]:
                title = entry.get("title", "").strip()
                if not title:
                    continue

                summary = entry.get("summary", entry.get("description", ""))
                if summary:
                    from bs4 import BeautifulSoup
                    summary = BeautifulSoup(summary, "html.parser").get_text()[:500]

                link = entry.get("link", "")
                published = entry.get("published", entry.get("updated", ""))
                pub_date = parse_date(published) if published else datetime.now(timezone.utc)

                # Extract thumbnail from RSS media content
                thumbnail_url = ""
                media = entry.get("media_content", [])
                if media and isinstance(media, list):
                    for m in media:
                        if isinstance(m, dict) and m.get("url"):
                            thumbnail_url = m["url"]
                            break
                if not thumbnail_url:
                    media_thumb = entry.get("media_thumbnail", [])
                    if media_thumb and isinstance(media_thumb, list):
                        for m in media_thumb:
                            if isinstance(m, dict) and m.get("url"):
                                thumbnail_url = m["url"]
                                break
                if not thumbnail_url:
                    # Try to get image from enclosures
                    enclosures = entry.get("enclosures", [])
                    for enc in enclosures:
                        if isinstance(enc, dict) and "image" in enc.get("type", ""):
                            thumbnail_url = enc.get("href", enc.get("url", ""))
                            break

                article = {
                    "article_id": generate_article_id(title, feed_info["name"]),
                    "title": title,
                    "summary": summary or "",
                    "source": feed_info["name"],
                    "source_url": link,
                    "category": feed_info["category"],
                    "published_at": pub_date.isoformat(),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "tickers": [],
                    "sentiment": None,
                    "sentiment_score": None,
                    "thumbnail_url": thumbnail_url,
                }
                articles.append(article)
    except Exception as e:
        logger.error(f"Error fetching feed {feed_info['name']}: {e}")

    return articles


async def fetch_all_feeds() -> List[Dict]:
    tasks = [fetch_single_feed(feed) for feed in RSS_FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles = []
    for result in results:
        if isinstance(result, list):
            all_articles.extend(result)

    if all_articles:
        # Run FinBERT Batch inference on the scraped general news
        titles = [art["title"] for art in all_articles]
        sentiments = await analyze_sentiments_batch(titles)
        
        for art, sent in zip(all_articles, sentiments):
            art["sentiment"] = sent["label"]
            art["sentiment_score"] = sent["score"]

    # Embed articles into semantic news store for agent RAG
    try:
        from agent_tools import embed_and_store_news
        # Group articles by ticker for embedding
        ticker_articles: dict = {}
        for art in all_articles:
            for t in art.get("tickers", []):
                ticker_articles.setdefault(t, []).append(art)
        for ticker, arts in ticker_articles.items():
            embed_and_store_news(ticker, arts)
        # Also embed general news under "MARKET" key
        embed_and_store_news("MARKET", all_articles)
    except Exception as e:
        logger.warning(f"News embedding error (non-fatal): {e}")

    logger.info(f"Fetched {len(all_articles)} articles from {len(RSS_FEEDS)} feeds")
    return all_articles



STOP_WORDS = {"the", "a", "an", "is", "in", "on", "at", "to", "for", "of", "and", "or", "but", "with", "from", "by", "as", "it", "this", "that", "was", "are", "were", "be", "been", "has", "have", "had"}

def get_word_set(text):
    import re
    words = re.findall(r'\b\w+\b', text.lower())
    return set(words) - STOP_WORDS

def is_similar(t1, t2):
    s1 = get_word_set(t1)
    s2 = get_word_set(t2)
    if not s1 or not s2: return False
    overlap = len(s1.intersection(s2))
    return (overlap / min(len(s1), len(s2))) > 0.6

async def store_articles(db, articles: List[Dict]) -> int:
    from datetime import timedelta
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        await db.news_articles.delete_many({"published_at": {"$lt": cutoff.isoformat()}})
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

    stored = 0
    for article in articles:
        try:
            # 1. Deduplication by URL
            article_url = article.get('source_url', article['article_id'])
            if not article_url: article_url = article['article_id']
            article['url'] = article_url
            
            # published_date field for TTL index compatibility
            article['published_date'] = datetime.fromisoformat(article['published_at'].replace("Z", "+00:00"))
            
            # 2. Similarity check
            pub_date = article['published_date']
            time_window_start = (pub_date - timedelta(hours=2)).isoformat()
            time_window_end = (pub_date + timedelta(hours=2)).isoformat()
            
            recent_articles = await db.news_articles.find({
                "published_at": {"$gte": time_window_start, "$lte": time_window_end}
            }).to_list(100)
            
            is_dup = False
            for old_art in recent_articles:
                if old_art.get("url") != article['url'] and is_similar(article['title'], old_art['title']):
                    is_dup = True
                    break
                    
            article['is_duplicate'] = is_dup
            
            await db.news_articles.update_one(
                {"url": article['url']},
                {"$set": article},
                upsert=True
            )
            stored += 1
        except Exception as e:
            logger.error(f"Error storing article: {e}")

    logger.info(f"Stored {stored} articles (some may be updates) out of {len(articles)}")
    return stored

