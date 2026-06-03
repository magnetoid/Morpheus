"""Template helper for the vendor account-nav tile."""

# ruff: noqa: PLC0415
# Inline import keeps this module importable before the app registry +
# marketplace models are ready (templatetags load at startup).

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def vendor_for(user):
    """Return the user's Vendor row (any status) or None. Used to decide
    whether to show the 'Vendor dashboard' account tile."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    try:
        from plugins.installed.marketplace.models import Vendor

        return Vendor.objects.filter(user=user).only('id', 'status').first()
    except Exception:  # noqa: BLE001 — never break the account page
        return None
