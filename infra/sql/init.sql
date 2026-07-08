-- SINGLE SOURCE OF TRUTH: All schema changes must be made here and in Alembic migrations.
-- Do NOT add runtime CREATE TABLE/INDEX statements in service code.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'analyst',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS processed_articles (
    id SERIAL PRIMARY KEY,
    article_id INTEGER,
    title TEXT,
    content TEXT,
    source TEXT,
    published_at TIMESTAMP,
    ml_processed BOOLEAN DEFAULT FALSE,
    confidence FLOAT,
    sentiment VARCHAR(50),
    url TEXT,
    image_url TEXT,
    summary TEXT,
    topic VARCHAR(50),
    threat_score FLOAT DEFAULT 0,
    geopolitical_risk FLOAT DEFAULT 0,
    risk_level VARCHAR(20) DEFAULT 'low',
    content_hash VARCHAR(64),
    dedupe_key VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS extracted_entities (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES processed_articles(id) ON DELETE CASCADE,
    entity_text TEXT,
    entity_type VARCHAR(50),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS article_sentiments (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES processed_articles(id) ON DELETE CASCADE,
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
    evidence TEXT,
    source_article_ids INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence_history JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    topic VARCHAR(50),
    risk_score FLOAT DEFAULT 0,
    risk_level VARCHAR(20) DEFAULT 'low',
    confidence FLOAT DEFAULT 0,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    article_count INTEGER DEFAULT 0,
    cluster_key VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_articles (
    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    article_id INTEGER REFERENCES processed_articles(id) ON DELETE CASCADE,
    similarity_score FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, article_id)
);

CREATE TABLE IF NOT EXISTS event_entities (
    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    entity_text TEXT NOT NULL,
    entity_type VARCHAR(50),
    mention_count INTEGER DEFAULT 1,
    avg_confidence FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, entity_text)
);

CREATE TABLE IF NOT EXISTS entity_profiles (
    entity_text TEXT PRIMARY KEY,
    entity_type VARCHAR(50),
    aliases TEXT[] DEFAULT ARRAY[]::TEXT[],
    mention_frequency INTEGER DEFAULT 0,
    risk_trend FLOAT DEFAULT 0,
    associated_events INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    associated_relationships INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    executive_summary TEXT,
    key_actors JSONB DEFAULT '[]'::jsonb,
    key_events JSONB DEFAULT '[]'::jsonb,
    threat_assessment TEXT,
    confidence_score FLOAT DEFAULT 0,
    recommendations JSONB DEFAULT '[]'::jsonb,
    source_article_ids INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlists (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist_entities (
    watchlist_id INTEGER REFERENCES watchlists(id) ON DELETE CASCADE,
    entity_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (watchlist_id, entity_text)
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    watchlist_id INTEGER REFERENCES watchlists(id) ON DELETE CASCADE,
    entity_text TEXT,
    event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    alert_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    risk_score FLOAT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS article_embeddings (
    id SERIAL PRIMARY KEY,
    article_id INTEGER UNIQUE NOT NULL
        REFERENCES processed_articles(id)
        ON DELETE CASCADE,
    embedding vector(384) NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS case_items (
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    item_type VARCHAR(20) NOT NULL,
    item_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (case_id, item_type, item_id)
);

CREATE TABLE IF NOT EXISTS case_notes (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    note_text TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_processed_articles_dedupe_key ON processed_articles(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_processed_articles_published_at ON processed_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_processed_articles_topic ON processed_articles(topic);
CREATE INDEX IF NOT EXISTS idx_processed_articles_risk_level ON processed_articles(risk_level);
CREATE INDEX IF NOT EXISTS idx_processed_articles_sentiment ON processed_articles(sentiment);
CREATE INDEX IF NOT EXISTS idx_extracted_entities_article_id ON extracted_entities(article_id);
CREATE INDEX IF NOT EXISTS idx_extracted_entities_entity_text ON extracted_entities(entity_text);
CREATE INDEX IF NOT EXISTS idx_relationships_article_id ON relationships(article_id);
CREATE INDEX IF NOT EXISTS idx_relationships_source_entity ON relationships(source_entity);
CREATE INDEX IF NOT EXISTS idx_relationships_target_entity ON relationships(target_entity);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_events_topic ON events(topic);
CREATE INDEX IF NOT EXISTS idx_events_risk_score ON events(risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_events_last_seen ON events(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_event_articles_article_id ON event_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_event_entities_entity_text ON event_entities(entity_text);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_watchlist_entities_entity_text_lower ON watchlist_entities(LOWER(entity_text));
CREATE INDEX IF NOT EXISTS idx_event_entities_entity_text_lower ON event_entities(LOWER(entity_text));
CREATE INDEX IF NOT EXISTS idx_alerts_watchlist_event_entity_lower ON alerts(watchlist_id, event_id, LOWER(entity_text));
CREATE INDEX IF NOT EXISTS idx_cases_owner_id ON cases(owner_id);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_updated_at ON cases(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_case_items_case_id ON case_items(case_id);
CREATE INDEX IF NOT EXISTS idx_case_items_item_type ON case_items(item_type);
CREATE INDEX IF NOT EXISTS idx_case_notes_case_id ON case_notes(case_id);
CREATE INDEX IF NOT EXISTS idx_case_notes_created_by ON case_notes(created_by);
CREATE INDEX IF NOT EXISTS idx_article_embeddings_article_id ON article_embeddings(article_id);
CREATE INDEX IF NOT EXISTS idx_article_embeddings_embedding_hnsw ON article_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS copilot_conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    title TEXT NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS copilot_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES copilot_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Energy intelligence bridge tables

CREATE TABLE IF NOT EXISTS energy_entity_mappings (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES processed_articles(id) ON DELETE CASCADE,
    entity_text TEXT NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    energy_asset_type VARCHAR(50) NOT NULL,
    energy_asset_uuid UUID NOT NULL,
    energy_asset_name TEXT NOT NULL,
    energy_asset_slug TEXT NOT NULL,
    match_method VARCHAR(20) DEFAULT 'exact',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS article_energy_enrichments (
    id SERIAL PRIMARY KEY,
    article_id INTEGER UNIQUE NOT NULL REFERENCES processed_articles(id) ON DELETE CASCADE,
    locations JSONB DEFAULT '[]'::jsonb,
    infrastructure JSONB DEFAULT '[]'::jsonb,
    organizations JSONB DEFAULT '[]'::jsonb,
    commodities JSONB DEFAULT '[]'::jsonb,
    infrastructure_events JSONB DEFAULT '[]'::jsonb,
    context JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_energy_entity_mappings_article_id ON energy_entity_mappings(article_id);
CREATE INDEX IF NOT EXISTS idx_energy_entity_mappings_entity_text ON energy_entity_mappings(entity_text);
CREATE INDEX IF NOT EXISTS idx_energy_entity_mappings_asset_type ON energy_entity_mappings(energy_asset_type);
CREATE INDEX IF NOT EXISTS idx_energy_entity_mappings_asset_uuid ON energy_entity_mappings(energy_asset_uuid);
CREATE INDEX IF NOT EXISTS idx_article_energy_enrichments_article_id ON article_energy_enrichments(article_id);

CREATE INDEX IF NOT EXISTS idx_copilot_messages_conversation_id ON copilot_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_copilot_conversations_user_id ON copilot_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_copilot_conversations_updated_at ON copilot_conversations(updated_at DESC);
