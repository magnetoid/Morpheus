"""Template helpers for the advanced_ecommerce storefront blocks."""

# ruff: noqa: PLC0415
# Inline imports keep this module importable before the app registry +
# catalog/inventory models are ready (templatetags load at startup).

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def recently_viewed_product(slug: str):
    """Return a Product by slug or None. Used in the recently-viewed rail."""
    if not slug:
        return None
    try:
        from plugins.installed.catalog.models import Product

        return Product.objects.filter(slug=slug, status='active').select_related('category').first()
    except Exception:  # noqa: BLE001 — never break rendering
        return None


@register.simple_tag
def free_shipping_target():
    """Returns (target_amount, currency) tuple from plugin config."""
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('advanced_ecommerce')
        if plugin is None:
            return 40, 'USD'
        return (
            plugin.get_config_value('free_shipping_target', 40),
            plugin.get_config_value('free_shipping_currency', 'USD'),
        )
    except Exception:  # noqa: BLE001
        return 40, 'USD'


@register.simple_tag
def low_stock_threshold() -> int:
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('advanced_ecommerce')
        return int(plugin.get_config_value('low_stock_threshold', 5)) if plugin else 5
    except Exception:  # noqa: BLE001
        return 5


@register.simple_tag
def featured_collection_rails(exclude_slug: str = '', per_rail: int = 8, max_rails: int = 3):
    """Featured collections (with products) for the homepage rails.

    Each entry is ``{'collection': Collection, 'products': [Product, ...]}``.
    Driven by ``Collection.is_featured`` (merchants curate via the existing
    Collections admin). Skips empty collections and ``exclude_slug`` — the
    collection the home view already renders as the Staff-picks rail, so the
    two never duplicate. Caps come from plugin config. Returns [] when the
    rail is toggled off or anything goes wrong (never breaks the homepage).
    """
    try:
        from plugins.installed.catalog.models import Collection, Product
        from plugins.registry import app_registry

        plugin = app_registry.get('advanced_ecommerce')
        if plugin is not None:
            if not plugin.get_config_value('enable_collection_rails', True):
                return []
            per_rail = int(plugin.get_config_value('collection_rail_products', per_rail))
            max_rails = int(plugin.get_config_value('max_collection_rails', max_rails))

        rails = []
        collections = Collection.objects.filter(is_active=True, is_featured=True).order_by(
            'sort_order', 'name'
        )
        for collection in collections:
            if exclude_slug and collection.slug == exclude_slug:
                continue
            products = list(
                Product.objects.filter(status='active', collections=collection)
                .select_related('category')
                .prefetch_related('images')
                .order_by('-is_featured', '-created_at')[:per_rail]
            )
            if not products:
                continue
            rails.append({'collection': collection, 'products': products})
            if len(rails) >= max_rails:
                break
        return rails
    except Exception:  # noqa: BLE001 — never break homepage rendering
        return []


@register.simple_tag
def product_total_stock(product) -> int:
    """Sum of available stock across all variants of a product.

    The PDP hands storefront blocks the GraphQL product DICT, not the model —
    filtering `variant__product=<dict>` raised and the bare except returned 0,
    so the "Only N left" badge never rendered on a real product page. Resolve
    the id from either shape and filter by `variant__product_id` instead.
    """
    if product is None:
        return 0
    product_id = product.get('id') if isinstance(product, dict) else getattr(product, 'pk', None)
    if not product_id:
        return 0
    try:
        from plugins.installed.inventory.models import StockLevel

        total = 0
        for sl in StockLevel.objects.filter(variant__product_id=product_id):
            total += max(0, sl.quantity - sl.reserved_quantity)
        return total
    except Exception:  # noqa: BLE001
        return 0
