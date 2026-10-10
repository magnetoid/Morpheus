"""The visitor's consent decision, on every template context as ``consent``.

Contributed through ``register_context_processor`` so it disappears when the
app is disabled; the tag blocks it gates read it as
``{% if not consent.managed or consent.marketing %}`` — a store that does not
manage consent (GDPR features off, or the app off) keeps its tags.

Keys: ``managed`` (the store runs consent at all), ``decided`` (a decision is
on file, or the browser sent Global Privacy Control), ``decided_by_cookie``
(the visitor's own choice is on file), ``gpc`` (``Sec-GPC: 1``
was sent), and the per-category answer ``necessary`` / ``analytics`` /
``marketing`` / ``functional`` — necessary-only until the visitor opts in, and
an explicit choice beats the GPC signal.
"""

from __future__ import annotations

from plugins.installed.consent.services import (
    COOKIE_NAME,
    has_decided,
    is_gpc,
    read_consent_from_cookie,
)


def consent_context(request) -> dict:
    from core.context_processors import _gdpr_enabled  # noqa: PLC0415

    decision = read_consent_from_cookie(request)
    return {
        'consent': {
            'managed': _gdpr_enabled(),
            'decided': has_decided(request),
            'decided_by_cookie': COOKIE_NAME in (request.COOKIES or {}),
            'gpc': is_gpc(request),
            **decision,
        }
    }
