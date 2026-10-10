"""Template tags for the Web Stories app."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def webstory_embed_enabled() -> bool:
    """Settings → Storefront → Web Stories: show the story card on product pages."""
    from plugins.registry import app_registry  # noqa: PLC0415

    plugin = app_registry.get('webstories')
    if plugin is None:
        return False
    return bool(plugin.get_config_value('show_pdp_embed', True))
