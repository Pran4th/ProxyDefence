"""Unit tests for backend.shared.kafka.topics."""


class TestTOPICS:
    def test_has_required_topics(self):
        from backend.shared.kafka.topics import TOPICS
        assert "raw_articles" in TOPICS
        assert "processed_articles" in TOPICS

    def test_topic_config(self):
        from backend.shared.kafka.topics import TOPICS
        raw = TOPICS["raw_articles"]
        assert raw["partitions"] == 3
        assert raw["replication_factor"] == 1
        assert "cleanup.policy" in raw["config"]
        assert raw["config"]["cleanup.policy"] == "delete"

        processed = TOPICS["processed_articles"]
        assert processed["partitions"] == 3
        assert processed["replication_factor"] == 1
