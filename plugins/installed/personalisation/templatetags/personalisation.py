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
    """Check the consent cookie set by the consent plugin.

    Falls open in dev (no consent cookie present) — production behaviour
    is determined by settings.PERSONALISATION_REQUIRES_CONSENT (default
    True). The consent plugin sets `morph_consent` cookie with the JSON
    {'functional': bool, 'analytics': bool, 'marketing': bool}.
    """
    if request is None:
        return False
    raw = request.COOKIES.get('morph_consent', '')
    if not raw:
        # No banner-set cookie. Default: allow only if not enforced.
        from django.conf import settings  # noqa: PLC0415

        return not getattr(settings, 'PERSONALISATION_REQUIRES_CONSENT', True)
    return 'functional' in raw or 'all' in raw
