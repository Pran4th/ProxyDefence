from fastapi import FastAPI, HTTPException, Query
from confluent_kafka import Consumer
import json
import threading
import psycopg2
from elasticsearch import Elasticsearch
import os
import time
from psycopg2 import OperationalError as Psycopg2OpError
from elasticsearch.exceptions import ConnectionError as ElasticConnectionError
from typing import Optional
from fastapi import HTTPException, Query
from typing import Optional
# Set up logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

kafka_server = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
app = FastAPI(title="Database Service")

# Kafka configuration
conf = {
    'bootstrap.servers': kafka_server,
    'group.id': 'db-service-group',
    'auto.offset.reset': 'earliest',
    'session.timeout.ms': 6000
}

consumer = Consumer(conf)

# Database connection settings
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'defenseintel')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'admin')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'admin123')

# Elasticsearch connection
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'elasticsearch')

def get_postgres_connection(max_retries=5, delay=5):
    """Create a connection to PostgreSQL with retry logic"""
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                connect_timeout=3
            )
            logger.info("✅ Connected to PostgreSQL successfully")
            return conn
        except Psycopg2OpError as e:
            logger.error(f"❌ Attempt {attempt + 1}/{max_retries}: PostgreSQL connection failed - {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise

def get_elasticsearch_client(max_retries=5, delay=5):
    """Create a connection to Elasticsearch with retry logic"""
    for attempt in range(max_retries):
        try:
            # SIMPLE CONNECTION - Docker will resolve 'elasticsearch' hostname
            es = Elasticsearch(f"http://{ELASTICSEARCH_HOST}:9200")
            
            # Test the connection
            if es.ping():
                logger.info("✅ Connected to Elasticsearch successfully")
                return es
            else:
                logger.warning("⚠️ Elasticsearch ping failed, retrying...")
                continue
                
        except Exception as e:
            logger.error(f"❌ Attempt {attempt + 1}/{max_retries}: Elasticsearch connection failed - {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                logger.error("❌ Failed to connect to Elasticsearch after all retries")
                return None

def create_tables():
    """Create the necessary tables in PostgreSQL if they don't exist."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        # Create table for processed articles - UPDATED SCHEMA
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed_articles (
                id SERIAL PRIMARY KEY,
                article_id INTEGER,
                title TEXT,
                content TEXT,
                source TEXT,
                published_at TIMESTAMP,
                ml_processed BOOLEAN,
                confidence FLOAT,
                sentiment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Database tables created/verified")
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")

def save_to_postgres(data):
    """Save the processed article to PostgreSQL."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute(
    """
    INSERT INTO processed_articles (article_id, title, content, source, published_at, ml_processed, confidence, sentiment)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """,
    (
        data['id'],
        data['title'],
        data['content'],
        data['source'],
        data['published_at'],
        data.get('ml_processed', False),
        data.get('confidence', 0.0),  # ← Use correct field name
        data.get('sentiment', 'neutral')  # ← Add sentiment
    )
)
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Data saved to PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Error saving to PostgreSQL: {e}")

def save_to_elasticsearch(data):
    """Index the processed article in Elasticsearch."""
    try:
        es = get_elasticsearch_client()
        if es is None:
            logger.warning("⚠️ Elasticsearch not available, skipping indexing")
            return
            
        # Index the document in Elasticsearch - FIXED FIELDS
        es.index(
            index="processed_articles",
            document={
                "article_id": data['id'],
                "title": data['title'],
                "content": data['content'],
                "source": data['source'],
                "published_at": data['published_at'],
                "ml_processed": data.get('ml_processed', False),
                "confidence": data.get('confidence', 0.0),
                "sentiment": data.get('sentiment', 'neutral')
            }
        )
        logger.info("✅ Data indexed in Elasticsearch")
    except Exception as e:
        logger.error(f"❌ Error indexing in Elasticsearch: {e}")

def start_kafka_consumer():
    """Function to start listening to Kafka in a background thread."""
    logger.info("Database Service Kafka consumer starting...")
    
    try:
        consumer.subscribe(['processed_articles'])
        logger.info("Subscribed to processed_articles topic")
        
        while True:
            msg = consumer.poll(1.0)
            
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue

            final_data = json.loads(msg.value().decode('utf-8'))
            logger.info(f"📥 Received processed article: {final_data['title']}")
            
            # Save to databases
            save_to_postgres(final_data)
            save_to_elasticsearch(final_data)
            
    except Exception as e:
        logger.error(f"Error in Kafka consumer: {e}")
    finally:
        consumer.close()

@app.on_event("startup")
def startup_event():
    # Create database tables
    create_tables()
    # Start the Kafka consumer in a background thread
    threading.Thread(target=start_kafka_consumer, daemon=True).start()

@app.get("/")
def read_root():
    return {"message": "Database Service is Online and Consumer is Running"}

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test PostgreSQL connection
        conn = get_postgres_connection()
        conn.close()
        
        # Test Elasticsearch connection
        es = get_elasticsearch_client()
        es.info()
        
        return {
            "status": "healthy", 
            "postgres": "connected",
            "elasticsearch": "connected",
            "kafka": "consumer_running"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/api/articles")
def get_articles(limit: int = 20, offset: int = 0, sentiment: Optional[str] = None):
    """Get processed articles from PostgreSQL"""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        # Get column names for proper response formatting
        if sentiment:
            cur.execute(
                "SELECT * FROM processed_articles WHERE sentiment = %s ORDER BY published_at DESC LIMIT %s OFFSET %s",
                (sentiment, limit, offset)
            )
        else:
            cur.execute(
                "SELECT * FROM processed_articles ORDER BY published_at DESC LIMIT %s OFFSET %s",
                (limit, offset)
            )
        
        articles = cur.fetchall()
        
        # Convert to list of dictionaries
        columns = [desc[0] for desc in cur.description]
        result = []
        for row in articles:
            article_dict = dict(zip(columns, row))
            # Convert any non-serializable types
            if article_dict.get('published_at'):
                article_dict['published_at'] = article_dict['published_at'].isoformat()
            if article_dict.get('created_at'):
                article_dict['created_at'] = article_dict['created_at'].isoformat()
            result.append(article_dict)
        
        cur.close()
        conn.close()
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/analytics/summary")
def get_analytics_summary():
    """Get dashboard analytics"""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        # Total articles
        cur.execute("SELECT COUNT(*) FROM processed_articles")
        total_articles = cur.fetchone()[0]
        
        # Last 24 hours
        cur.execute("SELECT COUNT(*) FROM processed_articles WHERE published_at >= NOW() - INTERVAL '24 hours'")
        last_24h = cur.fetchone()[0] or 0
        
        # Average confidence
        cur.execute("SELECT AVG(confidence) FROM processed_articles")
        avg_confidence_result = cur.fetchone()[0]
        avg_confidence = float(avg_confidence_result) if avg_confidence_result else 0.0
        
        # Sentiment distribution
        cur.execute("SELECT sentiment, COUNT(*) as count FROM processed_articles GROUP BY sentiment")
        sentiment_rows = cur.fetchall()
        sentiment_dist = {row[0]: row[1] for row in sentiment_rows}
        
        cur.close()
        conn.close()
        
        return {
            "total_articles": total_articles,
            "articles_last_24h": last_24h,
            "avg_confidence": avg_confidence,
            "sentiment_distribution": sentiment_dist
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

@app.get("/api/search")
def search_articles(q: str = Query(..., min_length=2)):
    """Search articles (simple PostgreSQL search)"""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        search_term = f'%{q}%'
        cur.execute(
            "SELECT * FROM processed_articles WHERE title ILIKE %s OR content ILIKE %s ORDER BY published_at DESC LIMIT 20",
            (search_term, search_term)
        )
        
        articles = cur.fetchall()
        
        # Convert to list of dictionaries
        columns = [desc[0] for desc in cur.description]
        results = []
        for row in articles:
            article_dict = dict(zip(columns, row))
            if article_dict.get('published_at'):
                article_dict['published_at'] = article_dict['published_at'].isoformat()
            if article_dict.get('created_at'):
                article_dict['created_at'] = article_dict['created_at'].isoformat()
            results.append(article_dict)
        
        cur.close()
        conn.close()
        
        return {
            "query": q,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/api/articles/{article_id}")
def get_article(article_id: int):
    """Get a specific article by ID"""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM processed_articles WHERE id = %s", (article_id,))
        article = cur.fetchone()
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        # Convert to dictionary
        columns = [desc[0] for desc in cur.description]
        article_dict = dict(zip(columns, article))
        
        # Convert timestamps
        if article_dict.get('published_at'):
            article_dict['published_at'] = article_dict['published_at'].isoformat()
        if article_dict.get('created_at'):
            article_dict['created_at'] = article_dict['created_at'].isoformat()
        
        cur.close()
        conn.close()
        
        return article_dict
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")