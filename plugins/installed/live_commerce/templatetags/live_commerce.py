"""Storefront template tags for live_commerce."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def upcoming_live_event():
    """The event to tease on the storefront, or None. Self-hides the teaser block."""
    from plugins.installed.live_commerce import services

    return services.featured_teaser()
