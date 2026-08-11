"""Storefront plugin URLs (registered at prefix '') — these are the customer-
facing pages that get language-prefixed via i18n_patterns in morph/urls.py
(ADR 0022). Resolved lazily through include() so the plugin registry is fully
populated by the time this module is imported."""

from plugins.registry import app_registry

urlpatterns = app_registry.get_urlpatterns(storefront=True)
