"""Catalog tools — read-only product/category access for agents."""
from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


@tool(
    name='catalog.find_products',
    description='Search active products by free-text query. Returns up to `limit` matches with name, slug, price and short description.',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {
            'query': {'type': 'string', 'description': 'Search terms.'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 25, 'default': 8},
        },
        'required': ['query'],
    },
)
def find_products_tool(*, query: str, limit: int = 8) -> ToolResult:
    from django.db.models import Q
    from plugins.installed.catalog.models import Product

    q = (query or '').strip()
    if not q:
        return ToolResult(output={'products': []})
    limit = max(1, min(int(limit or 8), 25))
    qs = (
        Product.objects.filter(status='active')
        .filter(Q(name__icontains=q) | Q(short_description__icontains=q) | Q(sku__iexact=q))
        .order_by('-created_at')[:limit]
    )
    products = [
        {
            'id': str(p.id),
            'slug': p.slug,
            'name': p.name,
            'sku': p.sku,
            'price': str(getattr(p.price, 'amount', '')),
            'currency': str(getattr(p.price, 'currency', '')),
            'short_description': p.short_description or '',
            'url': f'/products/{p.slug}/',
        }
        for p in qs
    ]
    return ToolResult(output={'products': products}, display=f'{len(products)} match(es) for {q!r}')


@tool(
    name='catalog.get_product',
    description='Look up a single product by slug or SKU.',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'sku': {'type': 'string'},
        },
    },
)
def get_product_tool(*, slug: str = '', sku: str = '') -> ToolResult:
    from plugins.installed.catalog.models import Product

    if not slug and not sku:
        raise ToolError('Provide either slug or sku.')
    qs = Product.objects.filter(status='active')
    if slug:
        qs = qs.filter(slug=slug)
    if sku:
        qs = qs.filter(sku__iexact=sku)
    p = qs.first()
    if not p:
        return ToolResult(output={'product': None}, display='Not found')
    return ToolResult(output={'product': {
        'id': str(p.id),
        'slug': p.slug,
        'name': p.name,
        'sku': p.sku,
        'description': p.description or '',
        'short_description': p.short_description or '',
        'price': str(getattr(p.price, 'amount', '')),
        'currency': str(getattr(p.price, 'currency', '')),
        'category': p.category.name if p.category_id else '',
        'is_on_sale': bool(getattr(p, 'is_on_sale', False)),
    }})


@tool(
    name='catalog.list_categories',
    description='List top-level product categories.',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_categories_tool() -> ToolResult:
    from plugins.installed.catalog.models import Category

    cats = Category.objects.filter(parent__isnull=True).order_by('name')[:50]
    return ToolResult(output={
        'categories': [{'slug': c.slug, 'name': c.name} for c in cats],
    })


@tool(
    name='catalog.stats',
    description=(
        'Catalog-at-a-glance: total active / draft / archived product '
        'counts, breakdown by category, count missing primary images, '
        'and count flagged by the SEO audit. Use this when the merchant '
        'asks "how many products do we have", "what is the catalog '
        'status", or any catalog-wide summary question.'
    ),
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def catalog_stats_tool() -> ToolResult:
    from django.db.models import Count, Q
    from plugins.installed.catalog.models import Category, Product, ProductImage

    by_status = dict(
        Product.objects.values_list('status').annotate(c=Count('id')).values_list('status', 'c')
    )
    active_count = by_status.get('active', 0)
    draft_count = by_status.get('draft', 0)
    archived_count = by_status.get('archived', 0)

    # Per-category counts of active products. Categories with zero are
    # included so the merchant can spot empty buckets.
    cats = (
        Category.objects.filter(parent__isnull=True)
        .annotate(active=Count('products', filter=Q(products__status='active')))
        .order_by('name')
    )
    by_category = [{'slug': c.slug, 'name': c.name, 'active': c.active} for c in cats]

    products_with_image_ids = set(
        ProductImage.objects.filter(is_primary=True).values_list('product_id', flat=True).distinct()
    )
    missing_primary_image = (
        Product.objects.filter(status='active')
        .exclude(id__in=products_with_image_ids)
        .count()
    )

    return ToolResult(
        output={
            'active': active_count,
            'draft': draft_count,
            'archived': archived_count,
            'total': active_count + draft_count + archived_count,
            'by_category': by_category,
            'missing_primary_image': missing_primary_image,
        },
        display=(
            f'{active_count} active · {draft_count} draft · {archived_count} archived '
            f'· {missing_primary_image} missing primary image'
        ),
    )
