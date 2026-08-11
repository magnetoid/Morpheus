"""Template tags for the immersive PDP blocks."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def sticky_buybox_enabled():
    """Whether the merchant has the sticky buy box on (default True). Fail-soft —
    any config/DB problem returns True so the buy box still shows."""
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('immersive_pdp')
        return bool(plugin.get_config_value('sticky_buybox', True)) if plugin else True
    except Exception:  # noqa: BLE001, S110
        return True
