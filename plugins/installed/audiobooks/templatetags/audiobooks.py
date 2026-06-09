"""Storefront template tags for audiobooks."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def audiobook_for(product):
    """Return the ready Audiobook for a product (status='ready' + a file), else
    None. The PDP player block self-gates on this, so it renders nothing when
    there's no audiobook (or the plugin is disabled)."""
    if product is None:
        return None
    try:
        from plugins.installed.audiobooks.models import Audiobook

        return (
            Audiobook.objects.filter(variant__product=product, status='ready')
            .exclude(audio_file='')
            .select_related('variant')
            .first()
        )
    except Exception:  # noqa: BLE001 — never break the PDP over a missing audiobook
        return None
