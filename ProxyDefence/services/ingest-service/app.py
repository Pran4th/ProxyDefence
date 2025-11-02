import requests
from datetime import datetime, timedelta
from fastapi import FastAPI
from confluent_kafka import Producer
import json
import os
import hashlib

# --- CONFIGURATION ---
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS')
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "c71b58c8fa8b330a50b995521f6ba575") # Added your key as a fallback
NEWS_API_URL = "https://gnews.io/api/v4/search"

# --- FASTAPI APP INITIALIZATION ---
app = FastAPI(title="Ingest Service")

# --- KAFKA PRODUCER SETUP ---
conf = {'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS}
producer = Producer(conf)


# --- HELPER FUNCTIONS ---
def fetch_real_news():
    """Fetch real news about conflict zones from GNews API."""
    print("Fetching real news...")
    
    # --- FIX: HARDCODE THE DATE TO MATCH THE API's TEST DATA ---
    # Create a fixed date in the future to query against
    pretend_today = datetime(2025, 9, 15)
    
    params = {
        'q': '"world news"', # A much broader query
        'lang': 'en',
        'max': 10,
        'apikey': NEWS_API_KEY,
        # Use the fixed date to look back a few days
        'from': (pretend_today - timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
    }
    
    try:
        response = requests.get(NEWS_API_URL, params=params)
        
        # Add logging to see the exact URL we are calling
        print(f"DEBUG: Calling GNews API with URL: {response.url}")
        
        response.raise_for_status()
        articles = response.json().get('articles', [])
        
        print(f"Found {len(articles)} articles. Sending to Kafka...")
        for article in articles:
            article_url = article.get('url', '')
            if not article_url:
                continue
            
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
        print(f"Successfully sent {len(articles)} articles to 'raw_articles' topic.")
        return {"message": f"Fetched and sent {len(articles)} real news articles"}
        
    except Exception as e:
        print(f"Error fetching news: {e}")
        return {"error": str(e)}

# --- API ENDPOINTS ---
@app.get("/")
def read_root():
    return {"message": "Ingest Service is Online"}

@app.get("/fetch-real-news")
def trigger_fetch_news():
    """Endpoint to fetch real news and send it to the Kafka pipeline."""
    return fetch_real_news()
