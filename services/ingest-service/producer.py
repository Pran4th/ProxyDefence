from backend.shared.kafka import JsonProducer
from backend.shared.kafka.health import check_kafka_connection

producer = JsonProducer()

flush_producer = producer.flush
