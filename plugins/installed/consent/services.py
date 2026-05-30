"""Cookie + audit-log helpers for the consent plugin.

The decision lives in a single ``morpheus_consent`` cookie (JSON-encoded
365-day Secure / SameSite=Lax). Every write also lands in ``ConsentLog``
so the controller can demonstrate consent (GDPR Art. 7(1)).

Reads default to *necessary-only* when the cookie is missing — analytics
+ marketing must be off until the visitor actively opts in. That default
is the whole point of the plugin; do not change it.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from django.http import HttpRequest, HttpResponse

from plugins.installed.consent.models import ConsentLog

logger = logging.getLogger('morpheus.consent')

COOKIE_NAME = 'morpheus_consent'
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year per CNIL guidance.

DEFAULT_DECISION = {
    'necessary': True,
    'analytics': False,
    'marketing': False,
    'functional': False,
}


def read_consent_from_cookie(request: HttpRequest) -> dict[str, bool]:
    """Return the visitor's decision, defaulting to necessary-only.

    Tolerant of malformed cookies (returns the default) so a tampered
    value never crashes a storefront request.
    """
    raw = request.COOKIES.get(COOKIE_NAME) if request is not None else None
    if not raw:
        return dict(DEFAULT_DECISION)
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return dict(DEFAULT_DECISION)
    if not isinstance(data, dict):
        return dict(DEFAULT_DECISION)
    return {
        'necessary': True,  # always on — that's the contract.
        'analytics': bool(data.get('analytics')),
        'marketing': bool(data.get('marketing')),
        'functional': bool(data.get('functional')),
    }


def has_decided(request: HttpRequest) -> bool:
    """Has the visitor seen + answered the banner?"""
    return COOKIE_NAME in (request.COOKIES or {})


def _hash_ip(request: HttpRequest) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
    if not ip:
        return ''
    return hashlib.sha256(ip.encode('utf-8')).hexdigest()


def write_consent(
    request: HttpRequest,
    response: HttpResponse,
    *,
    analytics: bool,
    marketing: bool,
    functional: bool,
    customer: Any = None,
) -> dict[str, bool]:
    """Persist a decision on the response + in ConsentLog.

    Returns the normalized decision dict so callers can pass it to
    downstream tag-loading logic on the same request without re-reading.
    """
    decision = {
        'necessary': True,
        'analytics': bool(analytics),
        'marketing': bool(marketing),
        'functional': bool(functional),
    }
    response.set_cookie(
        COOKIE_NAME,
        json.dumps(decision, separators=(',', ':')),
        max_age=COOKIE_MAX_AGE,
        secure=not request.META.get('HTTP_HOST', '').startswith(('localhost', '127.0.0.1')),
        httponly=False,  # JS must read it to gate client-side tags.
        samesite='Lax',
    )
    try:
        if request.session.session_key is None:
            request.session.save()
        ConsentLog.objects.create(
            customer=customer if (customer is not None and getattr(customer, 'pk', None)) else None,
            session_key=(request.session.session_key or '')[:40],
            necessary=True,
            analytics=decision['analytics'],
            marketing=decision['marketing'],
            functional=decision['functional'],
            ip_hash=_hash_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT', '') or '')[:300],
        )
    except Exception:  # noqa: BLE001 — table missing pre-migration is non-fatal.
        logger.exception('consent: ConsentLog write failed (cookie still set)')
    return decision
