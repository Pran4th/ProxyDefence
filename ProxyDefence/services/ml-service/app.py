from fastapi import FastAPI
from confluent_kafka import Consumer, Producer
import json
import threading
import logging
from datetime import datetime
import os
from transformers import pipeline

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ML Service")

# Global variables
consumer = None
producer = None
sentiment_pipeline = None
ner_pipeline = None
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

def load_model():
    """Load the NLP models."""
    global sentiment_pipeline, ner_pipeline
    logger.info("Loading NLP models...")

    try:
        sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
        )

        logger.info("Loading NER model...")
        ner_pipeline = pipeline(
            "ner",
            model="dbmdz/bert-large-cased-finetuned-conll03-english",
            aggregation_strategy="simple",
        )

        logger.info("Models loaded successfully")
    except Exception as exc:
        sentiment_pipeline = None
        ner_pipeline = None
        logger.exception("Model loading failed, continuing in degraded mode: %s", exc)

def start_kafka_consumer():
    """Function to start listening to Kafka in a background thread."""
    global consumer, producer, sentiment_pipeline
    
    logger.info("ML Service Kafka consumer starting...")
    
    # Kafka configuration
    conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': 'ml-service-group',
        'auto.offset.reset': 'earliest',
        'session.timeout.ms': 6000
    }

    consumer = Consumer(conf)
    producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})
    
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
            
            # --- REAL ML PROCESSING ---
            processed_data = received_data.copy()
            processed_data['ml_processed'] = True
            processed_data['processed_at'] = datetime.utcnow().isoformat()
            
            title = processed_data.get('title', '')
            content = processed_data.get('content', '')
            # Truncate content to avoid token limit issues (DistilBERT limit is 512 tokens)
            full_text = f"{title}. {content}"[:1000] 
            
            if sentiment_pipeline:
                try:
                    # Run inference
                    result = sentiment_pipeline(full_text)[0]
                    # result is like {'label': 'POSITIVE', 'score': 0.99}
                    
                    label = result['label']
                    score = result['score']
                    
                    # Map to our sentiment categories
                    if label == 'NEGATIVE':
                        # High confidence negative sentiment is CRITICAL
                        processed_data['sentiment'] = 'negative'
                    elif label == 'POSITIVE':
                        processed_data['sentiment'] = 'positive'
                    else:
                        processed_data['sentiment'] = 'neutral'
                        
                    processed_data['confidence'] = float(score)
                    
                    # ENHANCEMENT: Add simple keyword flagging for 'Critical' threats
                    critical_keywords = ['nuclear', 'missile', 'genocide', 'chemical weapon', 'biological weapon']
                    if any(k in full_text.lower() for k in critical_keywords):
                        processed_data['sentiment'] = 'negative' # Force negative
                        processed_data['confidence'] = 0.99 # Boost confidence
                        logger.info(f"CRITICAL KEYWORD DETECTED: {title}")

                    logger.info(f"Analyzed sentiment: {processed_data['sentiment']} ({score:.2f})")
                    
                    # ENHANCEMENT: Extract Entities (Source/Target Detection)
                    entities = []
                    if ner_pipeline:
                        try:
                            ner_results = ner_pipeline(full_text)
                            # Filter for Locations (LOC) and Organizations (ORG)/Countries
                            # In CONLL03, LOC = Location, ORG = Organization, MISC = Miscellaneous (often nationalities)
                            
                            relevant_entities = [
                                {'text': e['word'], 'type': e['entity_group'], 'score': float(e['score'])}
                                for e in ner_results 
                                if e['entity_group'] in ['LOC', 'ORG', 'MISC'] and e['score'] > 0.85
                            ]
                            
                            # Deduplicate by text
                            seen = set()
                            unique_entities = []
                            for e in relevant_entities:
                                if e['text'] not in seen:
                                    unique_entities.append(e)
                                    seen.add(e['text'])
                            
                            processed_data['entities'] = unique_entities
                            logger.info(f"Extracted entities: {[e['text'] for e in unique_entities]}")
                            
                        except Exception as e:
                            logger.error(f"NER Inference error: {e}")
                            processed_data['entities'] = []

                except Exception as e:
                    logger.error(f"ML Inference error: {e}")
                    processed_data['sentiment'] = 'neutral'
                    processed_data['confidence'] = 0.0
            else:
                logger.warning("Model not loaded, skipping inference")
                processed_data['sentiment'] = 'neutral'
                processed_data['confidence'] = 0.0

            # Backward compatibility
            processed_data['fake_confidence'] = processed_data['confidence']
            
            # Send to processed_articles topic
            producer.produce('processed_articles', value=json.dumps(processed_data))
            producer.flush()
            
    except Exception as e:
        logger.error(f"Error in Kafka consumer: {e}")
    finally:
        if consumer:
            consumer.close()

@app.on_event("startup")
def startup_event():
    # Load model first
    load_model()
    # Start the Kafka consumer in a background thread
    threading.Thread(target=start_kafka_consumer, daemon=True).start()

@app.get("/")
def read_root():
    return {"message": "ML Service is Online (Transformers Enabled)"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "model_loaded": sentiment_pipeline is not None}
