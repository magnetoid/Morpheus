"""Which cart lines a coupon applies to.

A coupon may be limited to products, categories (with every category below
them, the rule in ``catalog/category_tree.py``) and collections, and may skip
lines that are already on sale. Until v0.150.0 nothing read those fields, so
a coupon meant for one shelf discounted the whole cart. The discount itself is
computed by the promotions app (it runs the cart's discount step); this module
only answers which lines count, for it and for the code box that refuses a
coupon nothing in the cart can use.
"""

from __future__ import annotations

from decimal import Decimal


def is_scoped(coupon) -> bool:
    """True when the coupon names products, categories or collections."""
    return (
        coupon.applicable_products.exists()
        or coupon.applicable_categories.exists()
        or coupon.applicable_collections.exists()
    )


def _on_sale(item) -> bool:
    """The line's price is below a compare-at price the catalog holds."""
    unit = Decimal(str(getattr(item.unit_price, 'amount', item.unit_price) or 0))
    for owner in (getattr(item, 'variant', None), getattr(item, 'product', None)):
        was = getattr(owner, 'compare_at_price', None) if owner is not None else None
        if was is not None and Decimal(str(was.amount)) > unit:
            return True
    return False


def eligible_items(coupon, items) -> list:
    """The cart lines ``coupon`` discounts: inside its scope (every line when it
    names none), minus lines on sale when it excludes them."""
    items = list(items)
    if coupon.exclude_sale_items:
        items = [it for it in items if not _on_sale(it)]
    if not items or not is_scoped(coupon):
        return items

    from plugins.installed.catalog.category_tree import subtree_ids

    product_ids = set(coupon.applicable_products.values_list('pk', flat=True))
    category_ids = subtree_ids(coupon.applicable_categories.all())
    collection_ids = set(coupon.applicable_collections.values_list('pk', flat=True))

    out = []
    for it in items:
        product = getattr(it, 'product', None)
        if product is None:
            continue
        if product.pk in product_ids:
            out.append(it)
            continue
        if category_ids and (
            product.category_id in category_ids
            or product.additional_categories.filter(pk__in=category_ids).exists()
        ):
            out.append(it)
            continue
        if collection_ids and product.collections.filter(pk__in=collection_ids).exists():
            out.append(it)
    return out


def line_total(items) -> Decimal:
    total = Decimal('0')
    for it in items:
        unit = Decimal(str(getattr(it.unit_price, 'amount', it.unit_price) or 0))
        total += unit * int(it.quantity or 0)
    return total


def refusal(coupon, items) -> str:
    """Why the code box should refuse ``coupon`` for these lines, or ''."""
    if not coupon.is_valid:
        return 'This code has expired or is no longer active.'
    if not eligible_items(coupon, items):
        return "This code doesn't apply to anything in your cart."
    return ''
