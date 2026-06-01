"""Lumina Book Creator landing page — a public storefront page at /create/."""

# ruff: noqa: PLC0415
# Inline registry import keeps the view import-light + avoids load-order coupling.

from __future__ import annotations

from morpheus.views import render


def landing(request):
    """Render the Lumina pitch within the active storefront theme.

    The CTA target (the Lumina book-creator app) is configurable via the
    plugin's settings panel; falls back to '#' when unset.
    """
    app_url = ''
    try:
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('lumina')
        if plugin is not None:
            app_url = plugin.get_config_value('app_url', '') or ''
    except Exception:  # noqa: BLE001 — config is optional; never break the page
        app_url = ''
    return render(
        request,
        'lumina/landing.html',
        {'lumina_app_url': app_url, 'active_nav': 'lumina'},
    )
