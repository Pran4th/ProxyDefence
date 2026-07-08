import asyncio
import socket

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


async def wait_for_service(
    host: str, port: int, timeout: float = 30, interval: float = 1
) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=interval
            )
            writer.close()
            await writer.wait_closed()
            logger.info("service_available", host=host, port=port)
            return
        except (OSError, asyncio.TimeoutError):
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(
                    f"Service at {host}:{port} not reachable within {timeout}s"
                )
            logger.debug("service_unavailable_retrying", host=host, port=port)
            await asyncio.sleep(interval)


async def wait_for_pg(pool, timeout: float = 30) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            logger.info("postgres_available")
            return
        except Exception:
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(
                    f"PostgreSQL not reachable within {timeout}s"
                )
            logger.debug("postgres_unavailable_retrying")
            await asyncio.sleep(1)


async def wait_for_es(client, timeout: float = 30) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            if await client.ping():
                logger.info("elasticsearch_available")
                return
        except Exception:
            pass

        if asyncio.get_event_loop().time() >= deadline:
            raise TimeoutError(
                f"Elasticsearch not reachable within {timeout}s"
            )
        logger.debug("elasticsearch_unavailable_retrying")
        await asyncio.sleep(1)


async def wait_for_kafka(servers: str, timeout: float = 30) -> None:
    from confluent_kafka.admin import AdminClient

    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            admin = AdminClient({"bootstrap.servers": servers})
            admin.list_topics(timeout=5)
            logger.info("kafka_available")
            return
        except Exception:
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(
                    f"Kafka at {servers} not reachable within {timeout}s"
                )
            logger.debug("kafka_unavailable_retrying")
            await asyncio.sleep(1)
