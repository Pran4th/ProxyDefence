from fastapi import FastAPI
from confluent_kafka import Consumer, Producer
import json
import threading
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ML Service")

# Global variables for Kafka clients
consumer = None
producer = None

def start_kafka_consumer():
    """Function to start listening to Kafka in a background thread."""
    global consumer, producer
    
    logger.info("ML Service Kafka consumer starting...")
    
    # Kafka configuration
    conf = {
        'bootstrap.servers': 'kafka:9092',
        'group.id': 'ml-service-group',
        'auto.offset.reset': 'earliest',
        'session.timeout.ms': 6000
    }

    consumer = Consumer(conf)
    producer = Producer({'bootstrap.servers': 'kafka:9092'})
    
    try:
        consumer.subscribe(['raw_articles'])
        logger.info("Subscribed to raw_articles topic")
        
        while True:
            msg = consumer.poll(1.0)
            
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue

            # Process the message
            received_data = json.loads(msg.value().decode('utf-8'))
            logger.info(f"Received article: {received_data.get('title', 'No Title')}")
            
            # Simple ML processing (replace with your actual ML logic)
            processed_data = received_data.copy()
            processed_data['ml_processed'] = True
            processed_data['processed_at'] = datetime.utcnow().isoformat()
            
            # Add simple sentiment (placeholder - replace with real ML)
            title = processed_data.get('title', '').lower()
            content = processed_data.get('content', '').lower()
            full_text = f"{title} {content}"
            
            # Simple sentiment analysis based on keywords
            negative_words = ['war', 'attack', 'conflict', 'crisis', 'kill', 'death', 'violence']
            positive_words = ['peace', 'agree', 'progress', 'solution', 'talk', 'diplomacy']
            
            if any(word in full_text for word in negative_words):
                processed_data['sentiment'] = 'negative'
                processed_data['confidence'] = 0.85
            elif any(word in full_text for word in positive_words):
                processed_data['sentiment'] = 'positive' 
                processed_data['confidence'] = 0.75
            else:
                processed_data['sentiment'] = 'neutral'
                processed_data['confidence'] = 0.70
            
            # ✅ CRITICAL FIX: Add fake_confidence field for database service compatibility
            processed_data['fake_confidence'] = processed_data['confidence']
            
            # Send to processed_articles topic
            producer.produce('processed_articles', value=json.dumps(processed_data))
            producer.flush()
            logger.info(f"Sent processed article: {processed_data.get('title', 'No Title')}")
            
    except Exception as e:
        logger.error(f"Error in Kafka consumer: {e}")
    finally:
        if consumer:
            consumer.close()

@app.on_event("startup")
def startup_event():
    # Start the Kafka consumer in a background thread
    logger.info("Starting ML Service without heavy ML models for now")
    threading.Thread(target=start_kafka_consumer, daemon=True).start()

@app.get("/")
def read_root():
    return {"message": "ML Service is Online and Consumer is Running"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ml-service"}