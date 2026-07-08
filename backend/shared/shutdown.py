import asyncio
import signal
from typing import Any, Awaitable, Callable

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class GracefulShutdown:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._callbacks: list[tuple[str, Callable[[], Awaitable[Any]]]] = []

    async def register(self, name: str, coro: Callable[[], Awaitable[Any]]) -> None:
        self._callbacks.append((name, coro))
        logger.debug("shutdown_callback_registered", name=name)

    async def shutdown(self) -> None:
        if not self._callbacks:
            logger.info("shutdown_no_callbacks")
            return

        logger.info(
            "shutdown_starting",
            callback_count=len(self._callbacks),
            timeout=self.timeout,
        )

        async def run_one(name: str, coro: Callable[[], Awaitable[Any]]) -> None:
            try:
                await coro()
                logger.info("shutdown_callback_ok", name=name)
            except Exception as exc:
                logger.error(
                    "shutdown_callback_failed",
                    name=name,
                    error=str(exc),
                )

        tasks = [run_one(name, coro) for name, coro in self._callbacks]
        done, pending = await asyncio.wait(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=self.timeout,
        )

        if pending:
            logger.warning(
                "shutdown_timeout",
                remaining=len(pending),
                timeout=self.timeout,
            )

        logger.info("shutdown_complete")


def install_signal_handlers(
    shutdown_handler: Callable[[], Awaitable[Any]],
) -> None:
    loop = asyncio.get_event_loop()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.ensure_future(_handle_signal(shutdown_handler)),
            )
    except NotImplementedError:
        logger.warning("signal_handlers_not_supported_on_this_platform")


async def _handle_signal(
    shutdown_handler: Callable[[], Awaitable[Any]],
) -> None:
    logger.info("signal_received", signal="SIGINT/SIGTERM")
    await shutdown_handler()
