"""Non-storefront plugin URLs (dashboard/, api/, payments/, …) — the 'chrome'
surfaces that must NEVER be language-prefixed (ADR 0022)."""

from plugins.registry import plugin_registry

urlpatterns = plugin_registry.get_urlpatterns(storefront=False)
