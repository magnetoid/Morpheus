"""Who a GA4 hit belongs to: the browser's own IDs, and the hashed customer.

A Measurement Protocol hit is only joined to the visitor's browser session when
it carries the IDs Google's tag wrote into the visitor's cookies. Without them
every server-side event is a new user with a new session and no traffic source
(until v0.127.0 every one was: the server minted a random client_id per hit).

* ``_ga`` holds the client ID: ``GA1.1.<random>.<timestamp>``, the last two parts.
* ``_ga_<stream>`` holds the session: ``GS1.1.<session_id>.…`` and, since 2025,
  ``GS2.1.s<session_id>$o…``.
"""

from __future__ import annotations

import re

from django.utils.crypto import salted_hmac

_SESSION = re.compile(r'^GS\d\.\d\.s?(\d+)')


def ga_ids(request, measurement_id: str = '') -> dict[str, str]:
    """``client_id`` and ``session_id`` from the visitor's GA cookies (either may be absent)."""
    cookies = getattr(request, 'COOKIES', None) or {}
    out: dict[str, str] = {}
    parts = (cookies.get('_ga') or '').split('.')
    if len(parts) >= 4 and parts[-2].isdigit() and parts[-1].isdigit():
        out['client_id'] = f'{parts[-2]}.{parts[-1]}'
    stream = (measurement_id or '').strip().upper()
    if stream.startswith('G-'):
        match = _SESSION.match(cookies.get(f'_ga_{stream[2:]}') or '')
        if match:
            out['session_id'] = match.group(1)
    return out


def user_id(pk) -> str:
    """The GA4 ``user_id`` for a signed-in customer: keyed on the store's secret,
    so it is stable for one customer and says nothing about who they are."""
    if pk in (None, ''):
        return ''
    return salted_hmac('morpheus.tracking.user_id', str(pk)).hexdigest()[:32]
