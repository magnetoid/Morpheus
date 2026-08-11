"""Non-storefront plugin URLs (dashboard/, api/, payments/, …) — the 'chrome'
surfaces that must NEVER be language-prefixed (ADR 0022)."""

from plugins.registry import app_registry

urlpatterns = app_registry.get_urlpatterns(storefront=False)
