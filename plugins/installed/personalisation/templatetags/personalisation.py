"""Templatetags for personalisation rails."""

from __future__ import annotations

from django import template

from plugins.installed.personalisation.services import related_to

register = template.Library()


@register.simple_tag(takes_context=True)
def frequently_bought(context, product, count: int = 4) -> list:
    """Return up to `count` Product instances most-bought-with `product`.

    Consent-gated: returns [] when the visitor hasn't given functional
    consent (recommendation-personalisation falls under "functional"
    cookies in GDPR Art. 7 reasoning).
    """
    request = context.get('request')
    if not _has_consent(request):
        return []
    if product is None:
        return []
    return related_to(product, k=int(count))


@register.simple_tag(takes_context=True)
def pairs_with(context, product, count: int = 10) -> list:
    """'Pairs with this' for the PDP — a dynamic blend of co-purchase +
    embedding similarity, reordered per visitor. The aggregate recommendations
    always show (not personal data); only the per-visitor ORDER is
    consent-gated, inside the service."""
    if product is None:
        return []
    from plugins.installed.personalisation.services import (  # noqa: PLC0415
        pairs_with as _pairs,
    )

    return _pairs(product, request=context.get('request'), k=int(count))


def _has_consent(request) -> bool:
    """Check the visitor's 'functional' consent via the consent plugin.

    Reads the ONE canonical consent cookie through
    ``consent.services.read_consent_from_cookie`` (single source of truth). This
    used to read a cookie named ``morph_consent`` that the consent banner never
    sets (it writes ``morpheus_consent``), so personalisation always fell back to
    the PERSONALISATION_REQUIRES_CONSENT default — silently disabled in prod.

    Falls open in dev when the banner hasn't been answered yet — production
    behaviour is governed by ``settings.PERSONALISATION_REQUIRES_CONSENT``
    (default True).
    """
    if request is None:
        return False
    try:
        from plugins.installed.consent.services import (  # noqa: PLC0415
            has_decided,
            read_consent_from_cookie,
        )

        if not has_decided(request):
            from django.conf import settings  # noqa: PLC0415

            return not getattr(settings, 'PERSONALISATION_REQUIRES_CONSENT', True)
        decision = read_consent_from_cookie(request)
        return bool(decision.get('functional') or decision.get('analytics'))
    except Exception:  # noqa: BLE001 — consent plugin missing/disabled → deny
        return False
