"""zero_search collector — subscribes to MorpheusEvents.SEARCH_PERFORMED.

Fires once per storefront search. We filter for `result_count == 0`
and emit a signal keyed on the normalised query so a popular
zero-result term shows as `seen_count=N` (not N rows).

That keyed-by-query fingerprint is exactly what the analyzer needs to
propose synonym mappings later (class 4 — zero_search → synonym).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.core.cache import cache
from django.utils import timezone

from core.self_improvement.services import emit_signal, fingerprint_for

logger = logging.getLogger('morpheus.self_improvement.zero_search')

SOURCE = 'zero_search'

# This handler runs synchronously on the PUBLIC, unauthenticated storefront
# search path (product_list fires SEARCH_PERFORMED). A zero-result miss mints a
# new SiSignal row keyed on the query, and dedup only collapses IDENTICAL
# strings — so a bot enumerating /products/?q=<random> would otherwise write an
# unbounded row per request. Cap emissions per hour so a flood is dropped
# cheaply (a cache INCR) before it reaches the DB; a real store's genuine
# zero-result searches sit far under the ceiling.
_HOURLY_CAP = 500

_NORMALISE = re.compile(r'\s+')


def _normalise_query(q: str) -> str:
    return _NORMALISE.sub(' ', q.strip().lower())[:200]


def _over_rate_cap() -> bool:
    """True once >_HOURLY_CAP misses have been recorded this hour. Fail-open on
    a cache outage — a Redis blip must not break search, and the emit itself
    stays fail-soft."""
    try:
        bucket = f'si:zero_search:cap:{timezone.now():%Y%m%d%H}'
        cache.add(bucket, 0, timeout=3700)
        return cache.incr(bucket) > _HOURLY_CAP
    except Exception:  # noqa: BLE001
        return False


def on_search_performed(*, query: str = '', result_count: int = -1, **_: Any) -> None:
    """Hook handler. Drops anything that returned at least one result;
    the analyzer only cares about misses."""
    if not query or result_count != 0:
        return

    normalised = _normalise_query(query)
    if not normalised:
        return

    if _over_rate_cap():
        return

    fp = fingerprint_for(SOURCE, normalised)
    try:
        emit_signal(
            source=SOURCE,
            fingerprint=fp,
            severity=55,  # actionable when it accumulates; low when it doesn't
            payload={'query': normalised},
        )
    except Exception:  # noqa: BLE001 — never break search on a signal write
        logger.exception('zero_search: emit_signal failed for query=%r', normalised)
