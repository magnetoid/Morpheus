"""Channel resolver.

`current_channel(request)` returns the StoreChannel matching the request's
host (falls back to default).
"""

from __future__ import annotations

from typing import Any

_UNSET = object()  # sentinel for the per-request channel memo


def current_channel(request) -> Any:
    from core.models import StoreChannel

    # Resolve once per request. Several context processors (display_currency,
    # channel_context) each call this on every request — without memoizing we'd
    # run StoreChannel.resolve_for_request (1-2 queries) two+ times for the same
    # answer. Cache on the request object: per-request scope means no cross-
    # request staleness and nothing to invalidate.
    if request is None:
        return StoreChannel.resolve_for_request(None)
    cached = getattr(request, '_morph_current_channel', _UNSET)
    if cached is _UNSET:
        cached = StoreChannel.resolve_for_request(request)
        request._morph_current_channel = cached
    return cached
