"""Shared helpers: logging and retry with exponential backoff."""

import functools
import logging
import time

from pipeline import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def with_retries(func):
    """Retry a flaky step (network calls) with exponential backoff: 2s, 4s, 8s...
    Raises the last error once retries are exhausted so the run fails loudly."""
    log = get_logger(func.__module__)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - we re-raise below
                if attempt == config.MAX_RETRIES:
                    log.error("%s failed after %d attempts: %s", func.__name__, attempt, exc)
                    raise
                wait = config.BACKOFF_SECONDS * 2 ** (attempt - 1)
                log.warning("%s attempt %d failed (%s); retrying in %.0fs",
                            func.__name__, attempt, exc, wait)
                time.sleep(wait)

    return wrapper
