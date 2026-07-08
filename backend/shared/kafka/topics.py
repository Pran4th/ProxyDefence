"""Canonical topic definitions and auto-creation.

Every topic the pipeline uses is defined here so nothing is hard-coded
in service code.
"""

TOPICS: dict[str, dict] = {
    "raw_articles": {
        "partitions": 3,
        "replication_factor": 1,
        "config": {"cleanup.policy": "delete", "retention.ms": "604800000"},
    },
    "processed_articles": {
        "partitions": 3,
        "replication_factor": 1,
        "config": {"cleanup.policy": "delete", "retention.ms": "604800000"},
    },
    "commodity_prices": {
        "partitions": 3,
        "replication_factor": 1,
        "config": {"cleanup.policy": "compact", "retention.ms": "2592000000"},  # 30 days
    },
    "ais_signals": {
        "partitions": 3,
        "replication_factor": 1,
        "config": {"cleanup.policy": "delete", "retention.ms": "604800000"},
    },
    "sanctions_updates": {
        "partitions": 2,
        "replication_factor": 1,
        "config": {"cleanup.policy": "compact", "retention.ms": "2592000000"},
    },
    "disruption_signals": {
        "partitions": 3,
        "replication_factor": 1,
        "config": {"cleanup.policy": "delete", "retention.ms": "604800000"},
    },
    "intelligence_alerts": {
        "partitions": 2,
        "replication_factor": 1,
        "config": {"cleanup.policy": "delete", "retention.ms": "2592000000"},
    },
}


def ensure_topics(bootstrap_servers: str | None = None) -> dict[str, str]:
    """Create topics that do not yet exist on the broker.

    Returns a dict mapping topic name to ``"created"`` or ``"already_exists"``.
    """
    from confluent_kafka.admin import AdminClient, NewTopic

    from backend.shared.kafka import KAFKA_BOOTSTRAP_SERVERS

    servers = bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
    admin = AdminClient({"bootstrap.servers": servers})

    existing = admin.list_topics(timeout=5).topics

    new_topics = []
    for name, spec in TOPICS.items():
        if name not in existing:
            new_topics.append(NewTopic(
                name,
                num_partitions=spec["partitions"],
                replication_factor=spec["replication_factor"],
                config=spec.get("config"),
            ))

    if not new_topics:
        return {name: "already_exists" for name in TOPICS}

    futures = admin.create_topics(new_topics)

    import logging
    logger = logging.getLogger(__name__)
    results: dict[str, str] = {}
    for topic_name, future in futures.items():
        try:
            future.result()
            results[topic_name] = "created"
            logger.info("topic_created", topic=topic_name)
        except Exception as exc:
            if "already exists" in str(exc).lower():
                results[topic_name] = "already_exists"
            else:
                results[topic_name] = f"error: {exc}"
                logger.error("topic_create_failed", topic=topic_name, error=str(exc))

    for name in TOPICS:
        if name not in results:
            results[name] = "already_exists"

    return results
