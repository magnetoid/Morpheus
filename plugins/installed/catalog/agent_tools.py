"""Catalog read tools for the agent layer.

products.search / products.get were migrated here from
core/assistant/tools/ecommerce.py so the Product queries live in the plugin that
owns them. Tool names + scopes are unchanged — Linda sources them by name from
the agent registry, so her prompts/skills keep resolving.
"""

from __future__ import annotations

from decimal import Decimal

from core.agents import ToolError, ToolResult, tool


def _money_str(value) -> str:
    if value is None:
        return ''
    amount = getattr(value, 'amount', value)
    try:
        return str(Decimal(str(amount)))
    except Exception:  # noqa: BLE001
        return str(amount)


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

    variants = [
        {
            'id': str(v.id),
            'name': getattr(v, 'name', ''),
            'sku': getattr(v, 'sku', ''),
            'price': _money_str(getattr(v, 'price', None)),
            'attributes': getattr(v, 'attributes', None) or {},
        }
        for v in p.variants.all()
    ]
    images = [
        {
            'id': str(img.id),
            'url': getattr(getattr(img, 'image', None), 'url', '')
            if getattr(img, 'image', None)
            else '',
            'alt': getattr(img, 'alt', ''),
            'is_primary': getattr(img, 'is_primary', False),
        }
        for img in p.images.all()
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
            'images': images,
            'stock_levels': stock_levels,
        }
    )
