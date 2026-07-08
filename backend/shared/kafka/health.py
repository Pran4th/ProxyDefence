"""Kafka connectivity health check — the only one in the codebase."""

from backend.shared.kafka import KAFKA_BOOTSTRAP_SERVERS, producer_config


def check_kafka_connection(
    bootstrap_servers: str | None = None,
) -> dict:
    """Probe whether Kafka is reachable.

    Returns a dict with ``status`` and either ``kafka_brokers`` or ``error``.
    """
    from confluent_kafka import Producer

    servers = bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
    try:
        producer = Producer(producer_config())
        producer.poll(timeout=0)
        return {"status": "healthy", "kafka_brokers": servers}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}
