-- 1. Create the PARENT table first
-- (This must exist before others can reference it)
CREATE TABLE IF NOT EXISTS processed_articles (
    id SERIAL PRIMARY KEY,
    article_id INTEGER, -- External ID from ingest
    title TEXT,
    content TEXT,
    source TEXT,
    published_at TIMESTAMP,
    ml_processed BOOLEAN DEFAULT FALSE,
    confidence FLOAT,
    sentiment VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Create CHILD tables afterwards
CREATE TABLE IF NOT EXISTS extracted_entities (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES processed_articles(id), -- Now this link works!
    entity_text TEXT,
    entity_type VARCHAR(50),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS article_sentiments (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES processed_articles(id), -- This works too!
    sentiment_label VARCHAR(20),
    sentiment_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS relationships (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES processed_articles(id) ON DELETE CASCADE,
    source_entity TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    relationship_type VARCHAR(50) NOT NULL,
    confidence FLOAT,
    context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_relationships_article_id
    ON relationships(article_id);

CREATE INDEX IF NOT EXISTS idx_relationships_source_entity
    ON relationships(source_entity);

CREATE INDEX IF NOT EXISTS idx_relationships_target_entity
    ON relationships(target_entity);

CREATE INDEX IF NOT EXISTS idx_relationships_type
    ON relationships(relationship_type);
