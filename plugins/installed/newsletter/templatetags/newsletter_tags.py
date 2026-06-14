"""Template tags for the newsletter storefront surface."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def active_signup_popup():
    """Return the most-recently-updated enabled SignupPopup, or None.

    Fail-soft: any error (table missing during migration, etc.) returns None so
    the storefront block simply renders nothing.
    """
    try:
        from plugins.installed.newsletter.models import SignupPopup

        return SignupPopup.objects.filter(enabled=True).order_by('-updated_at').first()
    except Exception:  # noqa: BLE001, S110
        return None
