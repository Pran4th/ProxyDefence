-- Add new tables for enhanced data storage
CREATE TABLE IF NOT EXISTS extracted_entities (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES processed_articles(id),
    entity_text TEXT,
    entity_type VARCHAR(50),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS article_sentiments (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES processed_articles(id),
    sentiment_label VARCHAR(20),
    sentiment_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);