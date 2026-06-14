"""Storefront template tags for product story blocks."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def product_story_blocks(slug):
    """Active story blocks for a product slug, ordered. Fail-soft → []."""
    try:
        from plugins.installed.product_stories.models import ProductStoryBlock

        return list(
            ProductStoryBlock.objects.filter(product__slug=slug, is_active=True).order_by('order')
        )
    except Exception:  # noqa: BLE001, S110 — table missing / bad slug → no blocks
        return []
