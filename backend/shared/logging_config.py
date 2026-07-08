import logging
import sys
import os
import structlog

from backend.shared.settings import settings

SERVICE_NAME = settings.SERVICE_NAME
LOG_LEVEL = settings.LOG_LEVEL


timestamper = structlog.processors.TimeStamper(fmt="iso")


def add_service_name(logger, method_name, event_dict):
    event_dict["service"] = SERVICE_NAME
    return event_dict


def setup_structlog(service_name: str | None = None) -> None:
    global SERVICE_NAME
    if service_name:
        SERVICE_NAME = service_name

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            add_service_name,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            timestamper,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer()
            if os.isatty(sys.stdout.fileno())
            else structlog.processors.JSONRenderer(),
        )
    )
    root_logger.addHandler(handler)
    root_logger.setLevel(LOG_LEVEL)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name or __name__)
