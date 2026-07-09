"""Unit tests for backend.shared.observability.metrics."""


class TestMetricDefinitions:
    def test_metrics_are_registered(self):
        from backend.shared.observability.metrics import (
            db_query_latency,
            pool_usage,
            pool_idle,
            memory_bytes,
            cpu_usage,
            startup_duration_seconds,
        )

        sample = list(db_query_latency.collect())
        assert sample

    def test_db_query_latency_labels(self):
        from backend.shared.observability.metrics import db_query_latency
        db_query_latency.labels(service="test", operation="select").observe(0.05)
        sample = list(db_query_latency.collect())
        assert sample

    def test_embedding_latency_defined(self):
        from backend.shared.observability.metrics import embedding_latency
        embedding_latency.labels(service="test").observe(0.1)

    def test_ml_inference_latency_defined(self):
        from backend.shared.observability.metrics import ml_inference_latency
        ml_inference_latency.labels(service="test", model_type="sentiment").observe(0.02)

    def test_kafka_lag_defined(self):
        from backend.shared.observability.metrics import kafka_lag
        kafka_lag.labels(group="test-group", topic="test-topic", partition="0").set(42)
