"""Lumina Book Creator landing page — a public storefront page at /create/."""

# ruff: noqa: PLC0415, S110
# Inline registry import keeps the view import-light + avoids load-order coupling.

from __future__ import annotations

from morpheus.app.views import render


def landing(request):
    """Render the Lumina pitch within the active storefront theme.

    The CTA target (the Lumina book-creator app) is configurable via the
    plugin's settings panel; defaults to the live Lumina app.
    """
    app_url = 'https://lumina.dotbooks.store'
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('lumina')
        if plugin is not None:
            app_url = plugin.get_config_value('app_url', '') or app_url
    except Exception:  # noqa: BLE001 — config is optional; keep the default
        pass
    return render(
        request,
        'lumina/landing.html',
        {'lumina_app_url': app_url, 'active_nav': 'lumina'},
    )
