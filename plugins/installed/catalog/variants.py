"""The variant that holds a product's stock when the product has no choices.

Stock is counted per variant (``inventory.StockLevel`` points at a
``ProductVariant``), so a product sold in one form needs one variant row to
count it. That row is the product's *default variant*: named "Default" (the
name Shopify gives the same row, "Default Title", counts too) and with no size,
so the product page shows no choice for it (``has_only_default_variant``) and
the product's own price stays the price (its price is left empty).
"""

from __future__ import annotations

from django.db import IntegrityError, transaction

DEFAULT_NAME = 'Default'
DEFAULT_VARIANT_NAMES = (DEFAULT_NAME, 'Default Title')

#: Product types that are never stocked: a download, and a booking.
UNSTOCKED_TYPES = ('digital', 'service')


def _active(product, variants=None) -> list:
    if variants is None:
        variants = product.variants.all()
    return [v for v in variants if getattr(v, 'is_active', True)]


def is_default_variant(variant) -> bool:
    """A row that only holds stock: the default name and no size."""
    return (variant.name or '').strip() in DEFAULT_VARIANT_NAMES and not (variant.size or '')


def has_only_default_variant(product, variants=None) -> bool:
    """True for a product with no choice to offer: not a variable product, and
    its one active variant is the default one. A product page shows no picker
    for it (every theme reads ``hasOnlyDefaultVariant``)."""
    if getattr(product, 'product_type', '') == 'variable':
        return False
    active = _active(product, variants)
    return len(active) == 1 and is_default_variant(active[0])


def stock_variant(product, variants=None):
    """The variant that counts a non-variable product's stock: its one active
    variant. ``None`` for a variable product, for one with several active
    variants (an order line must name which) and for one with none."""
    if product is None or getattr(product, 'product_type', '') == 'variable':
        return None
    active = _active(product, variants)
    return active[0] if len(active) == 1 else None


def ensure_stock_variant(product):
    """``stock_variant``, made when the product has no variant yet.

    The new row takes the product's SKU when no variant has it, else
    ``<sku or slug>-default``; its price stays empty, so the product's price is
    charged, and it ships when the product ships."""
    found = stock_variant(product)
    if found is not None:
        return found
    if getattr(product, 'product_type', '') in (*UNSTOCKED_TYPES, 'variable'):
        return None
    if _active(product):
        return None  # several variants: each counts its own stock
    from plugins.installed.catalog.models import ProductVariant

    base = (product.sku or product.slug or str(product.pk))[:90]
    for sku in (base, f'{base}-default', f'{base}-default-{str(product.pk)[:8]}'):
        if ProductVariant.objects.filter(sku=sku).exists():
            continue
        try:
            with transaction.atomic():
                return ProductVariant.objects.create(
                    product=product,
                    name=DEFAULT_NAME,
                    sku=sku,
                    requires_shipping=bool(getattr(product, 'requires_shipping', True)),
                    is_taxable=bool(getattr(product, 'is_taxable', True)),
                    weight=getattr(product, 'weight', None),
                )
        except IntegrityError:
            continue
    return None


#: The variant axes Google reads from a product group (`variesBy`), each with the
#: attribute names that state it. A variant's size is its own `size` field; a
#: variant attribute named "Size" stands in when that field is empty. Names are
#: compared on the attribute's slug or name, lowercased: English, plus "colour".
VARIANT_AXES: dict[str, tuple[str, ...]] = {
    'size': ('size',),
    'color': ('color', 'colour'),
    'material': ('material',),
    'pattern': ('pattern',),
}


def variant_axes(variant) -> dict[str, str]:
    """What a variant is on each axis Google reads: ``{'size': 'M', 'color': 'Red'}``.

    Only an attribute marked as a variant attribute (``Attribute.is_variant``)
    counts: a filterable "Material" on a product is a description, not one of
    its choices. An axis the variant says nothing about is left out.
    """
    out: dict[str, str] = {}
    size = (getattr(variant, 'size', '') or '').strip()
    if size:
        out['size'] = size
    try:
        values = list(variant.attribute_values.all())
    except Exception:  # noqa: BLE001 — an unsaved variant
        values = []
    for value in values:
        attribute = getattr(value, 'attribute', None)
        if attribute is None or not attribute.is_variant:
            continue
        names = {(attribute.slug or '').strip().lower(), (attribute.name or '').strip().lower()}
        for axis, accepted in VARIANT_AXES.items():
            text = (value.name or '').strip()
            if axis not in out and text and names & set(accepted):
                out[axis] = text
    return out
