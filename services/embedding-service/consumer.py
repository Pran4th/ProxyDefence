"""Standalone Kafka consumer that generates embeddings for processed articles."""
import asyncio
import signal
import sys

from confluent_kafka import Consumer

from backend.shared.kafka import consumer_config, json_deserializer
from backend.shared.logging_config import setup_structlog, get_logger

from config import EMBEDDING_MODEL_NAME
from db import get_pool, close_pool
from services.embeddings import embed_text, make_vector_str

setup_structlog("embedding-consumer")
logger = get_logger(__name__)

running = True
consumer_instance = None


async def store_embedding(pool, dedupe_key: str, vector) -> bool:
    vector_str = make_vector_str(vector)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM processed_articles WHERE dedupe_key = $1",
            dedupe_key,
        )
        if row is None:
            return False
        article_db_id = row["id"]
        result = await conn.execute(
            "INSERT INTO article_embeddings (article_id, embedding) VALUES ($1, $2::vector) ON CONFLICT (article_id) DO NOTHING",
            article_db_id,
            vector_str,
        )
    return "INSERT 0 1" in result


async def run():
    logger.info("consumer_creating_database_pool")
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    logger.info("consumer_database_pool_ready")

    embed_text("test")  # trigger model load
    logger.info("consumer_embedding_model_loaded", model=EMBEDDING_MODEL_NAME)

    consumer = Consumer(consumer_config("embedding-service-group"))
    consumer.subscribe(["processed_articles"])

    global consumer_instance
    consumer_instance = consumer
    logger.info("consumer_subscribed", topic="processed_articles")

    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error("consumer_error", error=str(msg.error()))
                continue

            try:
                article = json_deserializer(msg.value())
                dedupe_key = article.get("dedupe_key")
                if not dedupe_key:
                    logger.warning("article_missing_dedupe_key")
                    consumer.commit()
                    continue

                title = article.get("title", "") or ""
                content = article.get("content", "") or ""
                text = f"{title}\n\n{content}".strip()

                if not text:
                    logger.warning("empty_article_skipped", dedupe_key=dedupe_key)
                    consumer.commit()
                    continue

                vector = embed_text(text)
                stored = await store_embedding(pool, dedupe_key, vector)
                logger.info("embedding_processed", dedupe_key=dedupe_key, stored=stored)
                consumer.commit()

            except Exception as exc:
                logger.exception("embedding_processing_failed", error=str(exc))
                consumer.commit()

    finally:
        logger.info("consumer_shutting_down")
        if consumer:
            consumer.close()
        await close_pool()
        logger.info("consumer_shutdown_complete")


if __name__ == "__main__":
    def handle_signal(signum, frame):
        global running
        logger.info("consumer_signal_received", signal=signum)
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    asyncio.run(run())
    sys.exit(0)
