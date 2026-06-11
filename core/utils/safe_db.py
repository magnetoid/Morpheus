"""`@safe_db` — wrap a function so DatabaseError doesn't crash the caller.

Use sparingly: only on paths where the right answer to "the DB is down"
is to log + degrade gracefully (audit logging, telemetry mirroring,
hook handlers). Never wrap a path where silently swallowing a DB error
would corrupt state (ledger writes, payment captures, order placement).
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from django.db import DatabaseError

logger = logging.getLogger('morpheus.utils.safe_db')

T = TypeVar('T')


def safe_db(default: Any = None, *, log_level: int = logging.WARNING):
    """Catch DatabaseError, log, return `default`."""

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except DatabaseError as e:
                logger.log(
                    log_level,
                    'safe_db: %s.%s failed: %s',
                    fn.__module__,
                    fn.__qualname__,
                    e,
                )
                return default

        return wrapper

    return decorator
