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

    from plugins.registry import app_registry

    slug = str(
        app_registry.config_value('post_checkout_upsell', 'post_order_upsell_slug', '') or ''
    ).strip()
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
        from plugins.registry import app_registry

        image = product.primary_image
        default_copy = 'P.S. One more thing that pairs well.'
        copy = str(
            app_registry.config_value('post_checkout_upsell', 'post_order_copy', default_copy)
            or default_copy
        )
        return {
            'name': product.name,
            'slug': product.slug,
            'price': product.price,
            'image_url': getattr(getattr(image, 'image', None), 'url', '') if image else '',
            'copy': copy,
        }
    except Exception:  # noqa: BLE001 — a widget must never break the receipt
        return None
