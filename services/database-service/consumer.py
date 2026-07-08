"""Standalone Kafka consumer for database storage.

Runs as main process (not daemon thread), so Docker restart:always works.
"""

import sys

from backend.shared.kafka import ConsumerRunner, install_signal_handlers, json_deserializer
from backend.shared.logging_config import setup_structlog, get_logger

from db import create_pool, get_pool, close_pool
from services.database import upsert_article
from services.event_intelligence import replace_related_records, update_event_intelligence
from services.energy_enrichment import enrich_energy_context
from services.elastic_indexer import index_article

setup_structlog("database-service-consumer")
logger = get_logger(__name__)


def handle_message(msg) -> None:
    data = json_deserializer(msg.value())
    article_db_id = upsert_article(data)
    replace_related_records(article_db_id, data)
    update_event_intelligence(article_db_id)
    enrich_energy_context(article_db_id)
    index_article(data)


if __name__ == "__main__":
    create_pool()
    logger.info("database_pool_initialized")

    runner = ConsumerRunner("db-service-group", "processed_articles", handle_message)
    install_signal_handlers(runner)
    runner.run()
    close_pool()
    sys.exit(0)
