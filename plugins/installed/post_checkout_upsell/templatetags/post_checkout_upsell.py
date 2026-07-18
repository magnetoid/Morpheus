"""Template tags for the post-order upsell block.

``{% post_order_upsell_pick order as up %}`` resolves the merchant-configured
upsell product (settings panel → ``post_order_upsell_slug``), falling back to
the newest active product not already in the order. Returns a small dict the
block template renders, or ``None`` — the block self-hides. Fail-soft: any
error returns ``None`` rather than break the receipt page.
"""

from __future__ import annotations

from django import template

register = template.Library()


def _pick_product(order):
    from plugins.installed.catalog.models import Product

    in_order = set()
    if order is not None:
        in_order = {
            pid for pid in order.items.values_list('product_id', flat=True) if pid is not None
        }

    slug = ''
    try:
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('post_checkout_upsell')
        if plugin is not None:
            slug = str(plugin.get_config_value('post_order_upsell_slug', '') or '').strip()
    except Exception:  # noqa: BLE001 — config read must never break the receipt
        slug = ''

    if slug:
        product = Product.objects.filter(slug=slug, status='active').first()
        if product is not None and product.pk not in in_order:
            return product
    # Fallback: the newest active title the customer didn't just buy.
    return (
        Product.objects.filter(status='active')
        .exclude(pk__in=in_order)
        .order_by('-created_at')
        .first()
    )


@register.simple_tag
def post_order_upsell_pick(order):
    try:
        product = _pick_product(order)
        if product is None:
            return None
        image = product.primary_image
        copy = 'P.S. One more thing that pairs well.'
        try:
            from plugins.registry import plugin_registry

            plugin = plugin_registry.get('post_checkout_upsell')
            if plugin is not None:
                copy = str(plugin.get_config_value('post_order_copy', copy) or copy)
        except Exception:  # noqa: BLE001, S110 — default copy is fine
            pass
        return {
            'name': product.name,
            'slug': product.slug,
            'price': product.price,
            'image_url': getattr(getattr(image, 'image', None), 'url', '') if image else '',
            'copy': copy,
        }
    except Exception:  # noqa: BLE001 — a widget must never break the receipt
        return None
