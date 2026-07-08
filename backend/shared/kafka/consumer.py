"""Reusable Kafka consumer loop.

``ConsumerRunner`` encapsulates the poll-commit-signal lifecycle that
every service consumer was duplicating.  The service provides a handler
callable; the runner deals with the rest.
"""

import signal
from collections.abc import Callable

from confluent_kafka import Consumer

from backend.shared.kafka import consumer_config
from backend.shared.kafka.serialization import json_deserializer
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class ConsumerRunner:
    """Kafka consumer loop with signal handling, error recovery, and commit.

    Usage::

        def handle(msg):
            data = json_deserializer(msg.value())
            # ... business logic ...

        runner = ConsumerRunner("my-group", "my-topic", handle)
        runner.run()  # blocks until SIGINT/SIGTERM
    """

    def __init__(
        self,
        group_id: str,
        topic: str,
        on_message: Callable,
        *,
        config_override: dict | None = None,
        poll_timeout: float = 1.0,
    ):
        self._group_id = group_id
        self._topic = topic
        self._on_message = on_message
        self._poll_timeout = poll_timeout
        self._running = True

        config = consumer_config(group_id, **(config_override or {}))
        self._consumer = Consumer(config)
        self._consumer.subscribe([topic])

        logger.info(
            "consumer_initialized",
            group=group_id,
            topic=topic,
        )

    # ── public API ────────────────────────────────────────────────

    def run(self) -> None:
        """Start the consume loop.  Blocks until :meth:`stop` is called."""
        logger.info("consumer_started", group=self._group_id, topic=self._topic)
        try:
            while self._running:
                msg = self._consumer.poll(self._poll_timeout)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("consumer_poll_error", error=str(msg.error()))
                    continue

                try:
                    self._on_message(msg)
                except Exception:
                    logger.exception(
                        "consumer_handler_failed",
                        offset=msg.offset(),
                        topic=msg.topic(),
                    )
                finally:
                    self._consumer.commit()
        except KeyboardInterrupt:
            logger.info("consumer_interrupted")
        finally:
            self._consumer.close()
            logger.info("consumer_stopped", group=self._group_id)

    def stop(self) -> None:
        """Signal the loop to exit after the current poll."""
        self._running = False
        logger.info("consumer_stopping", group=self._group_id)

    # ── properties ───────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    @property
    def consumer(self) -> Consumer:
        return self._consumer


def install_signal_handlers(runner: ConsumerRunner) -> None:
    """Install SIGINT/SIGTERM handlers that call ``runner.stop()``.

    Usage::

        runner = ConsumerRunner(...)
        install_signal_handlers(runner)
        runner.run()
    """

    def _handler(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info("signal_received", signal=sig_name)
        runner.stop()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)
