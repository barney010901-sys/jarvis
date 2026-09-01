"""Shared logging setup.

Every module gets its logger via `logging.getLogger(__name__)` as usual;
this module only configures the root handler/formatter once, at app
startup, so log lines are consistently structured across the backend.
"""
import logging
import sys

from app.config import get_settings

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s :: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    root = logging.getLogger()
    root.setLevel(settings.jarvis_log_level.upper())
    root.handlers = [handler]

    _CONFIGURED = True
