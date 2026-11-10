"""Central logging configuration.

Call :func:`configure_logging` once during application startup.  The function is
idempotent so importing the app multiple times (for example in tests) does not
duplicate handlers.

The format is intentionally plain text: it is readable in a terminal, works
with uvicorn, and does not require a new dependency.  If you later add a log
aggregator, replace the formatter with JSON in one place.
"""

import logging
import sys


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Third-party libraries that are very chatty at INFO/DEBUG level.
_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "chromadb",
    "sentence_transformers",
    "transformers",
    "urllib3",
)

_configured = False


def configure_logging(level: str | int = "INFO") -> None:
    """Configure the root logger.

    ``level`` may be a name (``"INFO"``) or a numeric level.  Invalid names fall
    back to ``INFO`` instead of crashing the application at startup.
    """

    global _configured

    if isinstance(level, str):
        numeric_level = getattr(logging, level.upper(), logging.INFO)
    else:
        numeric_level = level

    root_logger = logging.getLogger()

    if not _configured:
        if not root_logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
            root_logger.addHandler(handler)

        for logger_name in _NOISY_LOGGERS:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

        _configured = True

    root_logger.setLevel(numeric_level)
