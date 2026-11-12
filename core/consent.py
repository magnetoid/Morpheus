"""Consent for what the server sends — one rule, read by every sender.

The browser-side rule (v0.91.0) is ``not consent.managed or consent.<category>``.
Server-side sends — conversion APIs, GA4 Measurement Protocol, audience uploads —
often run where no visitor is present (a payment webhook, a nightly job), so the
shopper's choice is recorded on the order at checkout (``metadata['consent']``)
and read back here.

Core never imports the consent app: it asks through ``CONSENT_DECISION`` and
``CONSENT_MARKETING_CUSTOMERS``. With the app off nothing answers, which reads
as "this store does not manage consent", exactly as the templates see it.
"""

from __future__ import annotations

CATEGORIES = ('analytics', 'marketing')
_UNMANAGED = {'managed': False, 'analytics': False, 'marketing': False}


def decision_for(request) -> dict:
    """The visitor's decision (``request=None``: no visitor, nothing granted)."""
    from core.hooks import MorpheusEvents, hook_registry

    answer = hook_registry.filter(MorpheusEvents.CONSENT_DECISION, None, request=request)
    if not isinstance(answer, dict):
        return dict(_UNMANAGED)
    return {
        'managed': bool(answer.get('managed')),
        'analytics': bool(answer.get('analytics')),
        'marketing': bool(answer.get('marketing')),
    }


def stamp(request) -> dict:
    """What an order records at checkout, read back by every later send."""
    return decision_for(request)


def _permits(decision: dict, category: str) -> bool:
    return not decision.get('managed') or bool(decision.get(category))


def allowed(category: str, *, order=None, request=None) -> bool:
    """May a server-side send of ``category`` data happen?

    The order's stamp decides when it has one; else the request's visitor; else
    the store: a store that manages consent refuses without evidence.
    """
    if category not in CATEGORIES:
        raise ValueError(f'unknown consent category: {category!r}')
    recorded = (getattr(order, 'metadata', None) or {}).get('consent') if order else None
    if isinstance(recorded, dict):
        return _permits(recorded, category)
    return _permits(decision_for(request), category)


# ── Where a visitor came from, carried through the banner ───────────────────
#
# The banner is a form POST that redirects back, so the first page an analytics
# session or GA4 sees after "Accept" has the store itself as its referrer, and
# every consenting visitor's search, social or AI referral was lost. The banner
# posts the page's own referrer and address; the consent app keeps them in this
# short-lived cookie, written only once analytics is allowed, and each reader
# (the analytics session, the GA4 tag) takes them from here.

ENTRY_COOKIE = 'morpheus_entry'
ENTRY_MAX_AGE = 120
_ENTRY_SALT = 'core.consent.entry'


def entry_cookie_value(referrer: str, landing: str) -> str:
    from django.core import signing

    return signing.dumps(
        {'r': (referrer or '')[:500], 'l': (landing or '')[:500]}, salt=_ENTRY_SALT, compress=True
    )


def entry(request) -> dict | None:
    """``{'referrer', 'landing'}`` the visitor arrived with, while the cookie is fresh."""
    from django.core import signing

    raw = (getattr(request, 'COOKIES', None) or {}).get(ENTRY_COOKIE)
    if not raw:
        return None
    try:
        data = signing.loads(raw, salt=_ENTRY_SALT, max_age=ENTRY_MAX_AGE)
    except signing.BadSignature:
        return None
    if not isinstance(data, dict) or not data.get('l'):
        return None
    return {'referrer': str(data.get('r') or ''), 'landing': str(data['l'])}


def marketing_customer_ids() -> set | None:
    """Customers whose latest decision allows marketing; ``None`` when the store
    does not manage consent (no restriction). Fails closed to an empty set."""
    from core.hooks import MorpheusEvents, hook_registry

    if not decision_for(None)['managed']:
        return None
    answer = hook_registry.filter(MorpheusEvents.CONSENT_MARKETING_CUSTOMERS, None)
    return set(answer) if answer is not None else set()
