"""Template helper for the affiliate account-nav tile."""

# ruff: noqa: PLC0415
# Inline import keeps this module importable before the app registry +
# affiliates models are ready (templatetags load at startup).

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def affiliate_for(user):
    """Return the user's Affiliate row (any status) or None. Used to decide
    whether to show the 'Affiliate dashboard' account tile."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    try:
        from plugins.installed.affiliates.models import Affiliate

        return Affiliate.objects.filter(user=user).only('id', 'status').first()
    except Exception:  # noqa: BLE001 — never break the account page
        return None
