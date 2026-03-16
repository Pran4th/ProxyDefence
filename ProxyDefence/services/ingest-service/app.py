import requests
from datetime import datetime, timedelta
from fastapi import FastAPI
from confluent_kafka import Producer
from apscheduler.schedulers.background import BackgroundScheduler
import json
import os
import hashlib
import logging

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "c71b58c8fa8b330a50b995521f6ba575")
NEWS_API_URL = "https://gnews.io/api/v4/search"

# --- FASTAPI APP INITIALIZATION ---
app = FastAPI(title="Ingest Service")

# --- KAFKA PRODUCER SETUP ---
conf = {'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS}
producer = Producer(conf)

# --- SCHEDULER SETUP ---
scheduler = BackgroundScheduler()

# --- KAFKA HEALTH CHECK ---
def check_kafka_connection() -> dict:
    """Check if Kafka is reachable by polling producer metadata."""
    try:
        producer.poll(timeout=0)
        return {"status": "healthy", "kafka_brokers": KAFKA_BOOTSTRAP_SERVERS}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# --- HELPER FUNCTIONS ---
def fetch_real_news():
    """Fetch real news about conflict zones from GNews API."""
    logger.info("Fetching real news...")
    
    today = datetime.utcnow()
    
    params = {
        'q': '"world news" OR "conflict" OR "war"',
        'lang': 'en',
        'max': 10,
        'apikey': NEWS_API_KEY,
        'from': (today - timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
    }
    
    try:
        response = requests.get(NEWS_API_URL, params=params)
        logger.debug(f"DEBUG: Calling GNews API with URL: {response.url}")
        
        response.raise_for_status()
        articles = response.json().get('articles', [])
        
        logger.info(f"Found {len(articles)} articles. Sending to Kafka...")
        for article in articles:
            article_url = article.get('url', '')
            if not article_url:
                continue
            
            # Create a deterministic ID
            article_id = int(hashlib.sha256(article_url.encode('utf-8')).hexdigest(), 16) % 10**8

            news_data = {
                "id": article_id,
                "title": article.get('title', ''),
                "content": article.get('content', '') or article.get('description', ''),
                "source": article.get('source', {}).get('name', 'Unknown'),
                "published_at": article.get('publishedAt', ''),
                "url": article.get('url', ''),
                "image": article.get('image', '')
            }
            producer.produce('raw_articles', value=json.dumps(news_data))
        
        producer.flush()
        logger.info(f"Successfully sent {len(articles)} articles to 'raw_articles' topic.")
        return {"message": f"Fetched and sent {len(articles)} real news articles"}
        
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return {"error": str(e)}

# --- LIFECYCLE EVENTS ---
@app.on_event("startup")
def startup_event():
    logger.info("Starting up Ingest Service...")
    # Add scheduled job: Fetch news every 1 hour
    scheduler.add_job(fetch_real_news, 'interval', hours=1, id='fetch_news_job')
    scheduler.start()
    logger.info("Scheduler started - Fetching news every 1 hour")

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
    logger.info("Scheduler shut down")

# --- API ENDPOINTS ---
@app.get("/")
def read_root():
    return {
        "message": "Ingest Service is Online",
        "scheduler_status": "Running" if scheduler.running else "Stopped",
        "jobs": [str(job) for job in scheduler.get_jobs()]
    }

@app.get("/health")
def health_check():
    return check_kafka_connection()

@app.get("/fetch-real-news")
def trigger_fetch_news():
    """Endpoint to fetch real news and send it to the Kafka pipeline."""
    return fetch_real_news()
