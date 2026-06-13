"""Cloudflare storefront template tags — the Turnstile widget."""

from __future__ import annotations

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def turnstile() -> str:
    """Render the Cloudflare Turnstile widget when enabled + a site key is set.
    Place inside a <form>; pair it with services.verify_turnstile() in the view.
    Renders nothing (so the form still works) when Turnstile is off."""
    from plugins.installed.cloudflare.services import turnstile_site_key  # noqa: PLC0415

    site = turnstile_site_key()
    if not site:
        return ''
    return mark_safe(  # noqa: S308 — site key is escape()'d; the rest is static markup
        f'<div class="cf-turnstile" data-sitekey="{escape(site)}" style="margin:.5rem 0;"></div>'
        '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
    )
