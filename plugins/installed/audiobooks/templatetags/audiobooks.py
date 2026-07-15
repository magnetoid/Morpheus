"""Storefront template tags for audiobooks."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def audiobook_for(product):
    """Return the ready Audiobook for a product (status='ready' + a file), else
    None. The PDP player block self-gates on this, so it renders nothing when
    there's no audiobook (or the plugin is disabled).

    The storefront PDP passes ``product`` as a GraphQL **dict**, while dashboard
    callers pass the model instance — resolve the id from either. (Filtering the
    FK by a dict raised, and the bare except swallowed it, so the player silently
    never rendered on the storefront.)
    """
    if product is None:
        return None
    pid = product.get('id') if isinstance(product, dict) else getattr(product, 'pk', product)
    if not pid:
        return None
    try:
        from plugins.installed.audiobooks.models import Audiobook

        return (
            Audiobook.objects.filter(variant__product_id=pid, status='ready')
            .exclude(audio_file='')
            .select_related('variant')
            .first()
        )
    except Exception:  # noqa: BLE001 — never break the PDP over a missing audiobook
        return None
