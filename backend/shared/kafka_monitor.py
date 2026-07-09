import logging

from backend.shared.settings import settings

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS

CONSUMER_GROUPS = {
    "ml-platform-consumer-group": "raw_articles",
    "db-service-group": "processed_articles",
    "embedding-service-group": "processed_articles",
}


def get_admin_client():
    from confluent_kafka.admin import AdminClient
    return AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})


async def get_consumer_lag() -> dict:
    try:
        admin = get_admin_client()
        group_names = list(CONSUMER_GROUPS.keys())
        future_map = admin.list_consumer_groups(requested_group_names=group_names, timeout=5)

        groups = {}
        for group_name, future in future_map.items():
            try:
                result = future.result()
                if result and result.group_name in CONSUMER_GROUPS:
                    topic = CONSUMER_GROUPS[result.group_name]
                    member_count = len(list(result.members)) if result.members else 0
                    groups[group_name] = {
                        "state": str(result.state),
                        "members": member_count,
                        "topic": topic,
                        "lag": "unknown",
                    }
            except Exception as e:
                groups[group_name] = {"state": "error", "error": str(e)}

        return groups
    except Exception as e:
        logger.warning("Failed to fetch consumer group info: %s", e)
        return {"error": str(e)}


async def get_consumer_lag_summary() -> dict:
    try:
        admin = get_admin_client()
        metadata = admin.list_topics(timeout=5)
        topics = {}
        for topic_name, topic_metadata in metadata.topics.items():
            if topic_name.startswith("_"):
                continue
            partitions = {}
            for partition_id, partition_metadata in topic_metadata.partitions.items():
                partitions[partition_id] = {
                    "leader": partition_metadata.leader,
                    "replicas": len(partition_metadata.replicas),
                }
            topics[topic_name] = {"partitions": partitions}

        committed = {}
        for group_name, topic in CONSUMER_GROUPS.items():
            try:
                future_map = admin.list_consumer_group_offsets(group_name, timeout=5)
                offsets = {}
                for tp, future in future_map.items():
                    try:
                        offset = future.result()
                        offsets[str(tp)] = offset.offset if offset else None
                    except Exception:
                        pass
                if offsets:
                    committed[group_name] = offsets
            except Exception:
                pass

        return {"topics": topics, "committed_offsets": committed}
    except Exception as e:
        logger.warning("Failed to fetch consumer lag details: %s", e)
        return {"error": str(e)}
