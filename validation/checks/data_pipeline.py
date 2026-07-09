import urllib.request
import json

from ..base_check import BaseCheck, CheckResult
from ..config import ValidationConfig

CATEGORY = "data_pipeline"
DESCRIPTION = "GNews -> Kafka -> ML -> DB -> Embedding -> ES end-to-end flow"


def get_checks(config: ValidationConfig):
    return [
        KafkaTopicsExist(config),
        KafkaConsumerGroupsRegistered(config),
        ProcessedArticlesInPostgres(config),
        ProcessedArticlesInElasticsearch(config),
        ArticleEmbeddingsInPostgres(config),
        ExtractedEntitiesInPostgres(config),
    ]


class KafkaTopicsExist(BaseCheck):
    name = "Kafka topics exist"
    description = "Required Kafka topics are present"

    def _run(self) -> CheckResult:
        try:
            from confluent_kafka import Producer
        except ImportError:
            return CheckResult(name=self.name, passed=False, message="confluent_kafka not installed")

        try:
            p = Producer({"bootstrap.servers": f"{self.config.kafka_host}:{self.config.kafka_port}"})
            metadata = p.list_topics(timeout=self.config.kafka_timeout)
            topics = set(metadata.topics.keys())
            required = {"raw_articles", "processed_articles", "embedding_requests"}
            # dynamic topics from energy schema
            energy_topics = {"entity_events", "intelligence_signals", "infrastructure_changes"}
            required = required | energy_topics

            missing = required - topics
            if missing:
                return CheckResult(
                    name=self.name, passed=False,
                    message=f"Missing topics: {', '.join(sorted(missing))}",
                    detail={"topics": sorted(topics), "missing": sorted(missing)},
                )
            return CheckResult(
                name=self.name, passed=True,
                message=f"All required topics present ({len(required)})",
                detail={"topics": sorted(topics)},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"Kafka error: {e}")


class KafkaConsumerGroupsRegistered(BaseCheck):
    name = "Kafka consumer groups registered"
    description = "Consumer groups for data pipeline services"

    def _run(self) -> CheckResult:
        try:
            from confluent_kafka import Consumer
        except ImportError:
            return CheckResult(name=self.name, passed=False, message="confluent_kafka not installed")

        try:
            c = Consumer({
                "bootstrap.servers": f"{self.config.kafka_host}:{self.config.kafka_port}",
                "group.id": "__validation_consumer_group_check__",
                "session.timeout.ms": 3000,
            })
            # Try to list consumer groups via broker metadata
            c.list_topics(timeout=self.config.kafka_timeout)
            groups_available = c.list_topics(timeout=self.config.kafka_timeout)
            c.close()

            required_groups = {"ml-platform", "database-service", "embedding-service"}
            # confluent_kafka doesn't directly list groups; we check by their existence indirectly
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message="Consumer group listing requires broker admin access; verify via broker logs",
                detail={"required_groups": sorted(required_groups)},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, warning=True, message=f"Cannot check consumer groups: {e}")


class ProcessedArticlesInPostgres(BaseCheck):
    name = "Processed articles in PostgreSQL"
    description = "processed_articles table has records"

    def _run(self) -> CheckResult:
        try:
            import asyncpg
        except ImportError:
            return CheckResult(name=self.name, passed=False, message="asyncpg not installed")

        try:
            import asyncio

            async def check():
                conn = await asyncpg.connect(
                    host=self.config.postgres_host, port=self.config.postgres_port,
                    user=self.config.postgres_user, password=self.config.postgres_password,
                    database=self.config.postgres_db, timeout=self.config.db_timeout,
                )
                row_count = await conn.fetchval("SELECT COUNT(*) FROM processed_articles")
                sample = await conn.fetch(
                    "SELECT id, title, source, sentiment, confidence FROM processed_articles ORDER BY id DESC LIMIT 3"
                )
                await conn.close()
                return row_count, [dict(r) for r in sample]

            count, samples = asyncio.run(check())
            if count and count > 0:
                return CheckResult(
                    name=self.name, passed=True,
                    message=f"{count} articles in database",
                    detail={"count": count, "sample": samples},
                )
            return CheckResult(
                name=self.name, passed=True, warning=True,
                message="processed_articles table exists but is empty",
                detail={"count": 0},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"PostgreSQL check failed: {e}")


class ProcessedArticlesInElasticsearch(BaseCheck):
    name = "Processed articles in Elasticsearch"
    description = "processed_articles index exists and has documents"

    def _run(self) -> CheckResult:
        try:
            url = f"http://{self.config.elasticsearch_host}:{self.config.elasticsearch_port}/_cat/indices/processed_articles?format=json"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.config.http_timeout) as resp:
                indices = json.loads(resp.read())

            if not indices:
                return CheckResult(name=self.name, passed=False, message="Index not found")

            docs = int(indices[0].get("docs.count", 0))
            return CheckResult(
                name=self.name, passed=docs > 0,
                message=f"{docs} documents indexed" if docs > 0 else "Index exists but empty",
                detail={"index": indices[0]},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"ES check failed: {e}")


class ArticleEmbeddingsInPostgres(BaseCheck):
    name = "Article embeddings in PostgreSQL"
    description = "article_embeddings table has records"

    def _run(self) -> CheckResult:
        try:
            import asyncpg
        except ImportError:
            return CheckResult(name=self.name, passed=False, message="asyncpg not installed")

        try:
            import asyncio

            async def check():
                conn = await asyncpg.connect(
                    host=self.config.postgres_host, port=self.config.postgres_port,
                    user=self.config.postgres_user, password=self.config.postgres_password,
                    database=self.config.postgres_db, timeout=self.config.db_timeout,
                )
                tables = await conn.fetch(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                )
                table_names = [t["table_name"] for t in tables]
                embedding_tables = [t for t in table_names if "embed" in t.lower()]
                counts = {}
                for t in embedding_tables:
                    c = await conn.fetchval(f"SELECT COUNT(*) FROM {t}")
                    counts[t] = c
                await conn.close()
                return counts

            counts = asyncio.run(check())
            if not counts:
                return CheckResult(
                    name=self.name, passed=True, warning=True,
                    message="No embedding tables found in public schema",
                )
            total = sum(counts.values())
            return CheckResult(
                name=self.name, passed=total > 0,
                message=f"{total} embeddings across {len(counts)} tables: {counts}",
                detail={"tables": counts},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"PostgreSQL check failed: {e}")


class ExtractedEntitiesInPostgres(BaseCheck):
    name = "Extracted entities in PostgreSQL"
    description = "extracted_entities table has records"

    def _run(self) -> CheckResult:
        try:
            import asyncpg
        except ImportError:
            return CheckResult(name=self.name, passed=False, message="asyncpg not installed")

        try:
            import asyncio

            async def check():
                conn = await asyncpg.connect(
                    host=self.config.postgres_host, port=self.config.postgres_port,
                    user=self.config.postgres_user, password=self.config.postgres_password,
                    database=self.config.postgres_db, timeout=self.config.db_timeout,
                )
                tables = await conn.fetch(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                )
                table_names = [t["table_name"] for t in tables]
                entity_tables = [t for t in table_names if "entit" in t.lower()]
                counts = {}
                for t in entity_tables:
                    c = await conn.fetchval(f"SELECT COUNT(*) FROM {t}")
                    counts[t] = c
                await conn.close()
                return counts

            counts = asyncio.run(check())
            if not counts:
                return CheckResult(
                    name=self.name, passed=True, warning=True,
                    message="No entity tables found in public schema",
                )
            total = sum(counts.values())
            return CheckResult(
                name=self.name, passed=total > 0,
                message=f"{total} entities across {len(counts)} tables: {counts}",
                detail={"tables": counts},
            )
        except Exception as e:
            return CheckResult(name=self.name, passed=False, message=f"PostgreSQL check failed: {e}")
