"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text(), unique=True, nullable=False),
        sa.Column("username", sa.Text(), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="analyst"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "processed_articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("ml_processed", sa.Boolean(), server_default="false"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("sentiment", sa.String(50), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(50), nullable=True),
        sa.Column("threat_score", sa.Float(), server_default="0"),
        sa.Column("geopolitical_risk", sa.Float(), server_default="0"),
        sa.Column("risk_level", sa.String(20), server_default="low"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("dedupe_key", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "extracted_entities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("processed_articles.id", ondelete="CASCADE")),
        sa.Column("entity_text", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "article_sentiments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("processed_articles.id", ondelete="CASCADE")),
        sa.Column("sentiment_label", sa.String(20), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "relationships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("processed_articles.id", ondelete="CASCADE")),
        sa.Column("source_entity", sa.Text(), nullable=False),
        sa.Column("target_entity", sa.Text(), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("source_article_ids", sa.ARRAY(sa.Integer()), server_default="ARRAY[]::INTEGER[]"),
        sa.Column("observed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("confidence_history", sa.JSON(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(50), nullable=True),
        sa.Column("risk_score", sa.Float(), server_default="0"),
        sa.Column("risk_level", sa.String(20), server_default="low"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("first_seen", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("article_count", sa.Integer(), server_default="0"),
        sa.Column("cluster_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "event_articles",
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("processed_articles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("similarity_score", sa.Float(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "event_entities",
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("entity_text", sa.Text(), nullable=False, primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("mention_count", sa.Integer(), server_default="1"),
        sa.Column("avg_confidence", sa.Float(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "entity_profiles",
        sa.Column("entity_text", sa.Text(), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("aliases", sa.ARRAY(sa.Text()), server_default="ARRAY[]::TEXT[]"),
        sa.Column("mention_frequency", sa.Integer(), server_default="0"),
        sa.Column("risk_trend", sa.Float(), server_default="0"),
        sa.Column("associated_events", sa.ARRAY(sa.Integer()), server_default="ARRAY[]::INTEGER[]"),
        sa.Column("associated_relationships", sa.ARRAY(sa.Integer()), server_default="ARRAY[]::INTEGER[]"),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("key_actors", sa.JSON(), server_default="[]"),
        sa.Column("key_events", sa.JSON(), server_default="[]"),
        sa.Column("threat_assessment", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), server_default="0"),
        sa.Column("recommendations", sa.JSON(), server_default="[]"),
        sa.Column("source_article_ids", sa.ARRAY(sa.Integer()), server_default="ARRAY[]::INTEGER[]"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET_NULL")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET_NULL")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "watchlist_entities",
        sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlists.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("entity_text", sa.Text(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlists.id", ondelete="CASCADE")),
        sa.Column("entity_text", sa.Text(), nullable=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="SET_NULL")),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("risk_score", sa.Float(), server_default="0"),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET_NULL")),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "article_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("processed_articles.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
    )

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET_NULL")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "case_items",
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("item_type", sa.String(20), nullable=False, primary_key=True),
        sa.Column("item_id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "case_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE")),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET_NULL")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index("idx_processed_articles_dedupe_key", "processed_articles", ["dedupe_key"], unique=True)
    op.create_index("idx_processed_articles_published_at", "processed_articles", ["published_at"], postgresql_using="btree")
    op.create_index("idx_processed_articles_topic", "processed_articles", ["topic"])
    op.create_index("idx_processed_articles_risk_level", "processed_articles", ["risk_level"])
    op.create_index("idx_processed_articles_sentiment", "processed_articles", ["sentiment"])
    op.create_index("idx_extracted_entities_article_id", "extracted_entities", ["article_id"])
    op.create_index("idx_extracted_entities_entity_text", "extracted_entities", ["entity_text"])
    op.create_index("idx_relationships_article_id", "relationships", ["article_id"])
    op.create_index("idx_relationships_source_entity", "relationships", ["source_entity"])
    op.create_index("idx_relationships_target_entity", "relationships", ["target_entity"])
    op.create_index("idx_relationships_type", "relationships", ["relationship_type"])
    op.create_index("idx_events_topic", "events", ["topic"])
    op.create_index("idx_events_risk_score", "events", ["risk_score"])
    op.create_index("idx_events_last_seen", "events", ["last_seen"])
    op.create_index("idx_event_articles_article_id", "event_articles", ["article_id"])
    op.create_index("idx_event_entities_entity_text", "event_entities", ["entity_text"])
    op.create_index("idx_alerts_status", "alerts", ["status"])
    op.create_index("idx_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("idx_cases_owner_id", "cases", ["owner_id"])
    op.create_index("idx_cases_status", "cases", ["status"])
    op.create_index("idx_cases_updated_at", "cases", ["updated_at"])
    op.create_index("idx_case_items_case_id", "case_items", ["case_id"])
    op.create_index("idx_case_items_item_type", "case_items", ["item_type"])
    op.create_index("idx_case_notes_case_id", "case_notes", ["case_id"])
    op.create_index("idx_case_notes_created_by", "case_notes", ["created_by"])
    op.create_index("idx_article_embeddings_article_id", "article_embeddings", ["article_id"])
    op.execute("CREATE INDEX IF NOT EXISTS idx_article_embeddings_embedding_hnsw ON article_embeddings USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_entities_entity_text_lower ON watchlist_entities(LOWER(entity_text))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_event_entities_entity_text_lower ON event_entities(LOWER(entity_text))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_watchlist_event_entity_lower ON alerts(watchlist_id, event_id, LOWER(entity_text))")


def downgrade() -> None:
    op.drop_table("case_notes")
    op.drop_table("case_items")
    op.drop_table("cases")
    op.drop_table("article_embeddings")
    op.drop_table("audit_logs")
    op.drop_table("alerts")
    op.drop_table("watchlist_entities")
    op.drop_table("watchlists")
    op.drop_table("reports")
    op.drop_table("entity_profiles")
    op.drop_table("event_entities")
    op.drop_table("event_articles")
    op.drop_table("events")
    op.drop_table("relationships")
    op.drop_table("article_sentiments")
    op.drop_table("extracted_entities")
    op.drop_table("processed_articles")
    op.drop_table("users")
