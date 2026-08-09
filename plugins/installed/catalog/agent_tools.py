"""Catalog agent tools (reads + write ops).

products.search / products.get were migrated here from
core/assistant/tools/ecommerce.py, and products.update_status /
products.update_price from ecommerce_writes.py (core→plugin boundary ratchet),
so the Product queries live in the plugin that owns them. Tool names + scopes +
gates are unchanged — Linda sources them by name from the agent registry, and
the shared confirm/staging helpers stay in core (plugin→core is the allowed
import direction). products.update_price keeps kind='pricing_change', which
core.safety CLASS_BLOCKLIST refuses at staging time — autonomous/staged runs
cannot propose price edits; the interactive confirmed flow still can.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from core.agents.guardrails import max_price_change_pct

# Shared write-gate helpers stay in core (imported by orders/metafields/cms
# too); plugin→core is the allowed import direction, so this is not a leak.
from core.assistant.tools.ecommerce_writes import (
    _is_staged,
    _obj_ref,
    _require_confirmed,
    _stage,
)
from morpheus.core import ToolError, ToolResult, tool
from morpheus.core import money_str as _money_str

# Cap for nested collections in products.get so a product with hundreds of
# variants/images can't dump every row into the model context; the untruncated
# total is reported alongside so the agent knows there's more.
_NESTED_CAP = 50


def _enforce_price_delta(old_amount, new_amount: Decimal, max_pct: float) -> None:
    """Refuse an agent price change whose magnitude exceeds the merchant's
    per-action cap (Settings → Agent guardrails). 0/unset = no cap. A change from
    an unset or zero base has an undefined percentage and is allowed — the cap
    bounds *changes*, not first prices."""
    if not max_pct or old_amount is None:
        return
    try:
        old = Decimal(str(old_amount))
    except (InvalidOperation, ValueError):
        return
    if old == 0:
        return
    pct = abs(new_amount - old) / old * 100
    if pct > Decimal(str(max_pct)):
        raise ToolError(
            f'price change of {pct:.0f}% exceeds the {max_pct:g}% per-action '
            f'limit ({old} → {new_amount}); adjust the price or raise the cap in '
            f'Settings → Agent guardrails'
        )


@tool(
    name='products.search',
    description=(
        'Search products. Filter by status (active/draft/archived), name '
        '(substring), sku (substring), category slug or vendor slug. Returns '
        '`total` (the real number of matching products in the catalogue) plus a '
        'sample of up to `limit` of them in `products` (newest first). To answer '
        '"how many products/books" use `total`, NOT the length of `products` — '
        'for an exact count without the sample, use products.count.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'status': {'type': 'string'},
            'name': {'type': 'string'},
            'sku': {'type': 'string'},
            'category': {'type': 'string'},
            'vendor': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def products_search_tool(
    *,
    status: str = '',
    name: str = '',
    sku: str = '',
    category: str = '',
    vendor: str = '',
    limit: int = 20,
) -> ToolResult:
    from plugins.installed.catalog.models import Product

    qs = Product.objects.select_related('category', 'vendor').all()
    if status:
        qs = qs.filter(status=status)
    if name:
        qs = qs.filter(name__icontains=name)
    if sku:
        qs = qs.filter(sku__icontains=sku)
    if category:
        qs = qs.filter(category__slug__iexact=category) | qs.filter(
            category__name__icontains=category
        )
    if vendor:
        qs = qs.filter(vendor__slug__iexact=vendor) | qs.filter(vendor__name__icontains=vendor)
    # Total matching the filters — counted BEFORE the limit, so the agent
    # reports the real catalogue size (e.g. 859), not the page size. The old
    # `count: len(rows)` made Linda say "20 books" for an 859-product store.
    total = qs.count()
    page = qs.order_by('-created_at')[: max(1, min(int(limit or 20), 50))]
    rows = [
        {
            'id': str(p.id),
            'name': p.name,
            'sku': p.sku or '',
            'slug': getattr(p, 'slug', ''),
            'status': p.status,
            'price': _money_str(getattr(p, 'price', None)),
            'currency': str(getattr(getattr(p, 'price', None), 'currency', '')),
            'category': getattr(p.category, 'name', '') if p.category_id else '',
            'vendor': getattr(p.vendor, 'name', '') if p.vendor_id else '',
            'product_type': getattr(p, 'product_type', ''),
        }
        for p in page
    ]
    return ToolResult(
        output={'products': rows, 'returned': len(rows), 'total': total},
        display=f'{len(rows)} of {total} product(s)',
    )


@tool(
    name='products.count',
    description=(
        'Count products in the catalogue, optionally filtered by status '
        '(active/draft/archived), category slug, or vendor slug. Returns the '
        'exact total. Use this to answer "how many products/books are there".'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'status': {'type': 'string'},
            'category': {'type': 'string'},
            'vendor': {'type': 'string'},
        },
    },
)
def products_count_tool(*, status: str = '', category: str = '', vendor: str = '') -> ToolResult:
    from django.db.models import Count

    from plugins.installed.catalog.models import Product

    qs = Product.objects.all()
    if status:
        qs = qs.filter(status=status)
    if category:
        qs = qs.filter(category__slug__iexact=category) | qs.filter(
            category__name__icontains=category
        )
    if vendor:
        qs = qs.filter(vendor__slug__iexact=vendor) | qs.filter(vendor__name__icontains=vendor)
    total = qs.count()
    by_status = dict(Product.objects.values_list('status').annotate(n=Count('id')))
    return ToolResult(
        output={'total': total, 'by_status': by_status},
        display=f'{total} product(s)',
    )


@tool(
    name='products.get',
    description=(
        'Fetch one product by id, sku, or slug — whichever is passed. '
        'Returns the product with variants, images, and stock levels.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'sku': {'type': 'string'},
            'slug': {'type': 'string'},
        },
    },
)
def products_get_tool(*, id: str = '', sku: str = '', slug: str = '') -> ToolResult:
    from plugins.installed.catalog.models import Product

    qs = Product.objects.select_related('category', 'vendor').prefetch_related('variants', 'images')
    p = None
    try:
        if id:
            p = qs.filter(pk=id).first()
        if p is None and sku:
            p = qs.filter(sku=sku).first()
        if p is None and slug:
            p = qs.filter(slug=slug).first()
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'lookup failed: {e}') from e
    if p is None:
        raise ToolError('product not found — pass id, sku, or slug')

    _all_variants = list(p.variants.all())
    variants = [
        {
            'id': str(v.id),
            'name': getattr(v, 'name', ''),
            'sku': getattr(v, 'sku', ''),
            'price': _money_str(getattr(v, 'price', None)),
            'attributes': getattr(v, 'attributes', None) or {},
        }
        for v in _all_variants[:_NESTED_CAP]
    ]
    _all_images = list(p.images.all())
    images = [
        {
            'id': str(img.id),
            'url': getattr(getattr(img, 'image', None), 'url', '')
            if getattr(img, 'image', None)
            else '',
            'alt': getattr(img, 'alt', ''),
            'is_primary': getattr(img, 'is_primary', False),
        }
        for img in _all_images[:_NESTED_CAP]
    ]

    # Stock levels — optional inventory plugin.
    stock_levels: list[dict] = []
    try:
        from plugins.installed.inventory.models import StockLevel

        for sl in StockLevel.objects.filter(variant__product=p).select_related(
            'variant', 'warehouse'
        ):
            stock_levels.append(
                {
                    'variant_sku': getattr(sl.variant, 'sku', ''),
                    'warehouse': getattr(sl.warehouse, 'name', '') if sl.warehouse_id else '',
                    'on_hand': sl.quantity,
                    'available': sl.available_quantity,
                }
            )
    except Exception:  # noqa: BLE001, S110
        pass

    return ToolResult(
        output={
            'id': str(p.id),
            'name': p.name,
            'sku': p.sku or '',
            'slug': getattr(p, 'slug', ''),
            'status': p.status,
            'price': _money_str(getattr(p, 'price', None)),
            'currency': str(getattr(getattr(p, 'price', None), 'currency', '')),
            'category': getattr(p.category, 'name', '') if p.category_id else '',
            'vendor': getattr(p.vendor, 'name', '') if p.vendor_id else '',
            'product_type': getattr(p, 'product_type', ''),
            'short_description': getattr(p, 'short_description', '')[:500],
            'description': getattr(p, 'description', '')[:2000],
            'meta_title': getattr(p, 'meta_title', ''),
            'meta_description': getattr(p, 'meta_description', ''),
            'variants': variants,
            'variants_total': len(_all_variants),
            'images': images,
            'images_total': len(_all_images),
            'stock_levels': stock_levels,
        }
    )


# ── i18n product-translation tools (migrated from core/i18n/agent_tools.py,
#    arch-debt refactor) — they query catalog.Product, so they belong here.
#    Names unchanged; core.i18n stays the translation service (plugin -> core).


@tool(
    name='i18n.translate_product',
    description="Set translations for a product's fields in a language.",
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'language_code': {'type': 'string', 'description': 'BCP-47 short code, e.g. "es"'},
            'name': {'type': 'string'},
            'short_description': {'type': 'string'},
            'description': {'type': 'string'},
        },
        'required': ['slug', 'language_code'],
    },
    requires_approval=True,
)
def translate_product_tool(
    *,
    slug: str,
    language_code: str,
    name: str = '',
    short_description: str = '',
    description: str = '',
) -> ToolResult:
    from core.i18n import bulk_set_translations
    from plugins.installed.catalog.models import Product

    try:
        product = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    n = bulk_set_translations(
        product,
        language_code,
        {'name': name, 'short_description': short_description, 'description': description},
    )
    return ToolResult(
        output={'product': slug, 'language': language_code, 'fields': n},
        display=f'Set {n} field(s) for {slug} in {language_code}',
    )


@tool(
    name='i18n.list_translations',
    description='Show all translations stored for a product (by slug).',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
)
def list_translations_tool(*, slug: str) -> ToolResult:
    from core.i18n import translations_for
    from plugins.installed.catalog.models import Product

    try:
        product = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    return ToolResult(output={'product': slug, 'translations': translations_for(product)})


# ── Write ops (migrated from core/assistant/tools/ecommerce_writes.py) ──


@tool(
    name='products.update_status',
    description=(
        "Set a product's status: active, draft, or archived. "
        'Pass either `id`, `sku`, or `slug` to identify the product.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'sku': {'type': 'string'},
            'slug': {'type': 'string'},
            'status': {'type': 'string', 'enum': ['active', 'draft', 'archived']},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['status'],
    },
    requires_approval=True,
    supports_staging=True,
)
def products_update_status_tool(
    *,
    status: str,
    id: str = '',
    sku: str = '',
    slug: str = '',
    confirmed: bool = False,
    context: dict | None = None,
) -> ToolResult:
    staged = _is_staged(context)
    if not staged:
        _require_confirmed(confirmed)
    if status not in ('active', 'draft', 'archived'):
        raise ToolError(f'invalid status: {status}')
    from plugins.installed.catalog.models import Product

    p = None
    if id:
        p = Product.objects.filter(pk=id).first()
    if p is None and sku:
        p = Product.objects.filter(sku=sku).first()
    if p is None and slug:
        p = Product.objects.filter(slug=slug).first()
    if p is None:
        raise ToolError('product not found — pass id, sku, or slug')
    prev = p.status
    if staged:
        return _stage(
            context=context,
            tool_name='products.update_status',
            kind='product.update',
            title=f'Product "{p.name}": {prev} → {status}',
            summary=f'Set product {p.name!r} (SKU {p.sku}) status from {prev!r} to {status!r}.',
            changes=[{'object': _obj_ref(p), 'field': 'status', 'old': prev, 'new': status}],
            target=p,
        )
    p.status = status
    p.save(update_fields=['status', 'updated_at'])
    return ToolResult(
        output={
            'product_id': str(p.id),
            'name': p.name,
            'previous_status': prev,
            'new_status': status,
        },
        display=f'{p.name}: {prev} → {status}',
    )


@tool(
    name='products.update_price',
    description=(
        "Update a product's price (optionally on a specific variant). "
        'Pass `id`/`sku`/`slug` to find the product, optional '
        '`variant_id` for a variant-specific change, and the new '
        '`price` as a numeric string ("19.99"). Currency stays the '
        'same. Requires `confirmed=True`.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'sku': {'type': 'string'},
            'slug': {'type': 'string'},
            'variant_id': {'type': 'string'},
            'price': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['price'],
    },
    requires_approval=True,
    supports_staging=True,
)
def products_update_price_tool(
    *,
    price: str,
    id: str = '',
    sku: str = '',
    slug: str = '',
    variant_id: str = '',
    confirmed: bool = False,
    context: dict | None = None,
) -> ToolResult:
    staged = _is_staged(context)
    if not staged:
        _require_confirmed(confirmed)
    try:
        amount = Decimal(str(price))
    except (InvalidOperation, ValueError) as e:
        raise ToolError(f'invalid price: {price}') from e
    if amount < 0:
        raise ToolError('price cannot be negative')
    max_pct = max_price_change_pct()

    from plugins.installed.catalog.models import Product, ProductVariant

    if variant_id:
        v = ProductVariant.objects.filter(pk=variant_id).first()
        if v is None:
            raise ToolError(f'variant not found: {variant_id}')
        prev = str(getattr(getattr(v, 'price', None), 'amount', ''))
        _enforce_price_delta(getattr(getattr(v, 'price', None), 'amount', None), amount, max_pct)
        if staged:
            # 'pricing_change' is in core.safety.CLASS_BLOCKLIST — staging
            # refuses it, deliberately: autonomous runs cannot propose price
            # edits (spec §2). The interactive confirmed flow still can.
            return _stage(
                context=context,
                tool_name='products.update_price',
                kind='pricing_change',
                title=f'Variant {v.sku}: {prev} → {amount}',
                summary=f'Change variant {v.sku} price from {prev} to {amount}.',
                changes=[
                    {'object': _obj_ref(v), 'field': 'price', 'old': prev, 'new': str(amount)}
                ],
                target=v,
            )
        # djmoney accepts a Decimal directly when assigned; the field's
        # currency is preserved from the existing value.
        v.price = amount
        v.save(update_fields=['price', 'updated_at'])
        return ToolResult(
            output={
                'variant_id': str(v.id),
                'sku': v.sku,
                'previous_price': prev,
                'new_price': str(amount),
            },
            display=f'variant {v.sku}: {prev} → {amount}',
        )

    p = None
    if id:
        p = Product.objects.filter(pk=id).first()
    if p is None and sku:
        p = Product.objects.filter(sku=sku).first()
    if p is None and slug:
        p = Product.objects.filter(slug=slug).first()
    if p is None:
        raise ToolError('product not found — pass id, sku, slug, or variant_id')
    prev = str(getattr(getattr(p, 'price', None), 'amount', ''))
    _enforce_price_delta(getattr(getattr(p, 'price', None), 'amount', None), amount, max_pct)
    if staged:
        # See the variant branch above — 'pricing_change' is blocklisted at
        # staging time (core.safety), so this surfaces as a tool error.
        return _stage(
            context=context,
            tool_name='products.update_price',
            kind='pricing_change',
            title=f'Product "{p.name}": {prev} → {amount}',
            summary=f'Change product {p.name!r} price from {prev} to {amount}.',
            changes=[{'object': _obj_ref(p), 'field': 'price', 'old': prev, 'new': str(amount)}],
            target=p,
        )
    p.price = amount
    p.save(update_fields=['price', 'updated_at'])
    return ToolResult(
        output={
            'product_id': str(p.id),
            'name': p.name,
            'previous_price': prev,
            'new_price': str(amount),
        },
        display=f'{p.name}: {prev} → {amount}',
    )
