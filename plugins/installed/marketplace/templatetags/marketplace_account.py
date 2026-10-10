"""Template helper for the vendor account-nav tile."""

# ruff: noqa: PLC0415
# Inline import keeps this module importable before the app registry +
# marketplace models are ready (templatetags load at startup).

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def vendor_for(user):
    """``{'status', 'noun'}`` for the signed-in vendor or applicant, else None.

    A vendor is a ``catalog.Vendor`` the user owns (status ``approved`` while it
    is active); an applicant has a ``VendorApplication`` (its status). This used
    to import a ``Vendor`` model marketplace does not define, filter on a ``user``
    field ``catalog.Vendor`` does not have, and swallow the error — so the tile
    never rendered for anyone.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    try:
        from plugins.installed.marketplace.portal import resolve, vendor_noun

        vendor, application = resolve(user)
        if vendor is not None:
            status = 'approved' if vendor.is_active else 'paused'
        elif application is not None:
            status = application.status
        else:
            return None
        return {'status': status, 'noun': vendor_noun()[0]}
    except Exception:  # noqa: BLE001 — never break the account page
        return None
