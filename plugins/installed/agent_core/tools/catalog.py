"""Catalog tools — read-only product/category access for agents."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


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
    return ToolResult(
        output={
            'product': {
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
            }
        }
    )


@tool(
    name='catalog.list_categories',
    description='List top-level product categories.',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_categories_tool() -> ToolResult:
    from plugins.installed.catalog.models import Category

    cats = Category.objects.filter(parent__isnull=True).order_by('name')[:50]
    return ToolResult(
        output={
            'categories': [{'slug': c.slug, 'name': c.name} for c in cats],
        }
    )


@tool(
    name='catalog.backfill_alt_text',
    description=(
        'Backfill content-aware alt text on ProductImage rows '
        '("Title by Author — book cover" / "back cover" / "interior page N"). '
        'Idempotent: skips images whose alt is already non-empty, '
        'non-generic, and not equal to the product name. Pass `force=True` '
        'to overwrite. Returns updated/skipped counts.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slugs': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Optional list of product slugs to restrict to.',
            },
            'force': {'type': 'boolean', 'default': False},
        },
    },
    requires_approval=True,
)
def backfill_alt_text_tool(*, slugs: list[str] | None = None, force: bool = False) -> ToolResult:
    import re as _re
    from io import StringIO

    from django.core.management import call_command

    buf = StringIO()
    kwargs = {'force': bool(force), 'stdout': buf, 'stderr': buf}
    if slugs:
        kwargs['slugs'] = ','.join(s for s in slugs if s)
    call_command('backfill_alt_text', **kwargs)
    out = buf.getvalue()
    summary = {}
    for token in ('updated', 'skipped'):
        m = _re.search(rf'{token}=(\d+)', out)
        if m:
            summary[token] = int(m.group(1))
    return ToolResult(
        output={'summary': summary, 'log_tail': out[-400:]},
        display=f'updated={summary.get("updated", 0)} skipped={summary.get("skipped", 0)}',
    )


@tool(
    name='catalog.publish_digital_product',
    description=(
        'Publish a digital product (PDF book) to the catalog. The agent '
        'supplies HTTPS URLs for the PDF and (optionally) the cover '
        'image; Morpheus downloads both server-side, creates the Product '
        'with product_type="digital", and returns id + slug + storefront '
        'URL. Status defaults to "active" — the product is live on the '
        'storefront immediately.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'title': {'type': 'string', 'description': 'Book title.'},
            'pdf_url': {'type': 'string', 'description': 'HTTPS URL of the PDF (max 50 MB).'},
            'price_amount': {'type': 'string', 'description': 'Decimal price, e.g. "9.99".'},
            'price_currency': {'type': 'string', 'default': 'USD'},
            'description': {
                'type': 'string',
                'description': 'Long product description (Markdown ok).',
            },
            'short_description': {'type': 'string'},
            'author': {
                'type': 'string',
                'description': 'Author name; prepended to description if absent.',
            },
            'cover_image_url': {
                'type': 'string',
                'description': 'Optional HTTPS URL of cover (jpg/png/webp, max 8 MB).',
            },
            'category_slug': {'type': 'string'},
            'sku': {
                'type': 'string',
                'description': 'Optional; auto-generated from title if blank.',
            },
            'slug': {
                'type': 'string',
                'description': 'Optional; auto-generated from title if blank.',
            },
            'status': {
                'type': 'string',
                'enum': ['draft', 'active', 'archived'],
                'default': 'active',
            },
        },
        'required': ['title', 'pdf_url', 'price_amount'],
    },
)
def publish_digital_product_tool(
    *,
    title: str,
    pdf_url: str,
    price_amount: str,
    price_currency: str = 'USD',
    description: str = '',
    short_description: str = '',
    author: str = '',
    cover_image_url: str = '',
    category_slug: str = '',
    sku: str = '',
    slug: str = '',
    status: str = 'active',
) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, publish_digital_product

    try:
        result = publish_digital_product(
            title=title,
            pdf_url=pdf_url,
            price_amount=price_amount,
            price_currency=price_currency,
            description=description,
            short_description=short_description,
            author=author,
            cover_image_url=cover_image_url,
            category_slug=category_slug,
            sku=sku,
            slug=slug,
            status=status,
        )
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(
        output=result,
        display=f'Published {result["name"]!r} → {result["url"]} (sku={result["sku"]})',
    )


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
        Product.objects.filter(status='active').exclude(id__in=products_with_image_ids).count()
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


# ─── Create / edit / archive / delete / category tools ───────────────────────


@tool(
    name='catalog.create_product',
    description=(
        'Create a new product. Required: name, price_amount. status '
        'defaults to "draft" so half-built rows do not accidentally go '
        'live. For digital PDF books prefer catalog.publish_digital_product '
        '(also downloads + attaches the PDF). Returns the created '
        'product summary.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'price_amount': {'type': 'string', 'description': 'Decimal price, e.g. "9.99".'},
            'price_currency': {'type': 'string', 'default': 'USD'},
            'product_type': {
                'type': 'string',
                'enum': ['simple', 'variable', 'digital', 'bundle'],
                'default': 'simple',
            },
            'status': {
                'type': 'string',
                'enum': ['draft', 'active', 'archived'],
                'default': 'draft',
            },
            'sku': {'type': 'string', 'description': 'Auto-generated if blank.'},
            'slug': {'type': 'string', 'description': 'Auto-generated from name if blank.'},
            'short_description': {'type': 'string'},
            'description': {'type': 'string'},
            'category_slug': {'type': 'string'},
            'cover_image_url': {
                'type': 'string',
                'description': 'Optional HTTPS URL for the primary image.',
            },
            'weight': {'type': 'string'},
            'weight_unit': {'type': 'string'},
            'requires_shipping': {'type': 'boolean'},
            'is_featured': {'type': 'boolean'},
            'is_taxable': {'type': 'boolean'},
            'track_inventory': {'type': 'boolean'},
            'meta_title': {'type': 'string'},
            'meta_description': {'type': 'string'},
            'focus_keyword': {'type': 'string'},
            'canonical_url': {'type': 'string'},
            'noindex': {'type': 'boolean'},
            'nofollow': {'type': 'boolean'},
        },
        'required': ['name', 'price_amount'],
    },
)
def create_product_tool(
    *,
    name: str,
    price_amount: str,
    price_currency: str = 'USD',
    product_type: str = 'simple',
    status: str = 'draft',
    **extra,
) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, create_product

    # Drop Nones / empties so the service applies its own defaults.
    kwargs = {k: v for k, v in extra.items() if v not in (None, '')}
    try:
        r = create_product(
            name=name,
            price_amount=price_amount,
            price_currency=price_currency,
            product_type=product_type,
            status=status,
            **kwargs,
        )
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(
        output=r,
        display=f'Created {r["name"]!r} ({r["slug"]}, {r["product_type"]}, {r["status"]})',
    )


_PRICE_FIELDS = ('price_amount', 'price_currency')


def _refuse_price_change(fields: dict) -> None:
    """A price edit belongs to products.update_price, never to a generic update.

    That tool carries the approval gate and the merchant's per-action price
    cap (max_price_change_pct); applying a price here would be a second,
    ungated path around both.
    """
    if any(fields.get(k) not in (None, '') for k in _PRICE_FIELDS):
        raise ToolError(
            'Prices are changed with products.update_price (it applies the '
            'approval gate and the price-change cap). Nothing was updated.'
        )


@tool(
    name='catalog.update_product',
    description=(
        'Update any field on an existing product (lookup by slug). Every '
        'argument is optional — only the fields you pass are touched. '
        'Useful for changing status, editing description, re-categorising, '
        'or flipping SEO flags. Price changes go through '
        'products.update_price. Returns the updated product summary.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string', 'description': 'Product slug to update.'},
            'name': {'type': 'string'},
            'sku': {'type': 'string'},
            'status': {'type': 'string', 'enum': ['draft', 'active', 'archived']},
            'product_type': {'type': 'string', 'enum': ['simple', 'variable', 'digital', 'bundle']},
            'short_description': {'type': 'string'},
            'description': {'type': 'string'},
            'price_amount': {'type': 'string', 'description': 'Decimal price, e.g. "9.99".'},
            'price_currency': {'type': 'string'},
            'compare_at_amount': {'type': 'string', 'description': 'Pass "" or "null" to clear.'},
            'cost_amount': {'type': 'string', 'description': 'Pass "" or "null" to clear.'},
            'category_slug': {'type': 'string', 'description': 'Pass "" to clear.'},
            'weight': {'type': 'string'},
            'weight_unit': {'type': 'string'},
            'requires_shipping': {'type': 'boolean'},
            'is_featured': {'type': 'boolean'},
            'is_taxable': {'type': 'boolean'},
            'track_inventory': {'type': 'boolean'},
            'meta_title': {'type': 'string'},
            'meta_description': {'type': 'string'},
            'focus_keyword': {'type': 'string'},
            'canonical_url': {'type': 'string'},
            'noindex': {'type': 'boolean'},
            'nofollow': {'type': 'boolean'},
        },
        'required': ['slug'],
    },
)
def update_product_tool(*, slug: str, **fields) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, update_product

    _refuse_price_change(fields)
    try:
        r = update_product(slug=slug, **fields)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(
        output=r,
        display=f'Updated {r["name"]!r} ({r["slug"]}) — fields: {sorted(fields.keys())}',
    )


@tool(
    name='catalog.archive_product',
    description='Mark a product as archived (hides from storefront, keeps history).',
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
)
def archive_product_tool(*, slug: str) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, archive_product

    try:
        r = archive_product(slug=slug)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(output=r, display=f'Archived {r["slug"]}')


@tool(
    name='catalog.restore_product',
    description='Restore an archived product back to draft or active.',
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'status': {'type': 'string', 'enum': ['draft', 'active'], 'default': 'active'},
        },
        'required': ['slug'],
    },
)
def restore_product_tool(*, slug: str, status: str = 'active') -> ToolResult:
    from plugins.installed.catalog.services import PublishError, restore_product

    try:
        r = restore_product(slug=slug, status=status)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(output=r, display=f'Restored {r["slug"]} → {r["status"]}')


@tool(
    name='catalog.delete_product',
    description=(
        'Hard-delete a product. Prefer catalog.archive_product unless you '
        'really need the row gone — analytics + audit lose history on delete.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
    requires_approval=True,
)
def delete_product_tool(*, slug: str) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, delete_product

    try:
        r = delete_product(slug=slug)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(output=r, display=f'Deleted {r["slug"]}')


@tool(
    name='catalog.update_digital_pdf',
    description=(
        'Replace the digital PDF file on an existing product. The new '
        'PDF is downloaded server-side from `pdf_url` (HTTPS-only, max '
        '50 MB) and attached. Use when an agent has a fresh revision '
        'of a book and needs to swap the customer download.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'pdf_url': {'type': 'string'},
        },
        'required': ['slug', 'pdf_url'],
    },
)
def update_digital_pdf_tool(*, slug: str, pdf_url: str) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, update_digital_pdf

    try:
        r = update_digital_pdf(slug=slug, pdf_url=pdf_url)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(output=r, display=f'Updated PDF on {r["slug"]}')


@tool(
    name='catalog.add_product_image',
    description=(
        'Download an image from an HTTPS URL (jpg/png/webp/gif, max '
        '8 MB) and attach it as a ProductImage. Pass `is_primary=true` '
        'to demote any existing primary in the same call.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'image_url': {'type': 'string'},
            'alt_text': {'type': 'string'},
            'is_primary': {'type': 'boolean', 'default': False},
            'sort_order': {'type': 'integer', 'default': 0},
        },
        'required': ['slug', 'image_url'],
    },
)
def add_product_image_tool(
    *,
    slug: str,
    image_url: str,
    alt_text: str = '',
    is_primary: bool = False,
    sort_order: int = 0,
) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, add_product_image

    try:
        r = add_product_image(
            slug=slug,
            image_url=image_url,
            alt_text=alt_text,
            is_primary=is_primary,
            sort_order=sort_order,
        )
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(
        output=r,
        display=f'Added image to {r["product_slug"]}' + (' (primary)' if r['is_primary'] else ''),
    )


@tool(
    name='catalog.remove_product_image',
    description='Remove a ProductImage by id.',
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {'image_id': {'type': 'string'}},
        'required': ['image_id'],
    },
)
def remove_product_image_tool(*, image_id: str) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, remove_product_image

    try:
        r = remove_product_image(image_id=image_id)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(output=r, display=f'Removed image {image_id}')


@tool(
    name='catalog.set_primary_image',
    description='Promote an image to primary; demotes any other primary on the same product.',
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {'image_id': {'type': 'string'}},
        'required': ['image_id'],
    },
)
def set_primary_image_tool(*, image_id: str) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, set_primary_image

    try:
        r = set_primary_image(image_id=image_id)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(output=r, display=f'Set {image_id} as primary')


@tool(
    name='catalog.create_category',
    description='Create a new product category. parent_slug is optional (top-level if blank).',
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'slug': {'type': 'string', 'description': 'Auto-generated from name if blank.'},
            'parent_slug': {'type': 'string'},
            'description': {'type': 'string'},
        },
        'required': ['name'],
    },
)
def create_category_tool(
    *,
    name: str,
    slug: str = '',
    parent_slug: str = '',
    description: str = '',
) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, create_category

    try:
        r = create_category(name=name, slug=slug, parent_slug=parent_slug, description=description)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(output=r, display=f'Created category {r["name"]!r} ({r["slug"]})')


@tool(
    name='catalog.update_category',
    description='Update an existing category. Pass parent_slug="" to detach from parent.',
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'name': {'type': 'string'},
            'new_slug': {'type': 'string'},
            'parent_slug': {'type': 'string'},
            'description': {'type': 'string'},
        },
        'required': ['slug'],
    },
)
def update_category_tool(
    *,
    slug: str,
    name: str = '',
    new_slug: str = '',
    parent_slug: str | None = None,
    description: str | None = None,
) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, update_category

    try:
        r = update_category(
            slug=slug,
            name=name,
            new_slug=new_slug,
            parent_slug=parent_slug,
            description=description,
        )
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(output=r, display=f'Updated category {r["slug"]}')


@tool(
    name='catalog.create_variant',
    description=(
        'Create a new variant on an existing product. Required: '
        'product_slug, name, sku. Variant type controls fulfillment: '
        '"physical" ships, "digital" delivers a file, "virtual" is a '
        'service / gift card / booking (no shipment).'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'product_slug': {'type': 'string'},
            'name': {
                'type': 'string',
                'description': 'Human label, e.g. "Paperback" / "PDF" / "Audiobook MP3".',
            },
            'sku': {'type': 'string'},
            'price_amount': {'type': 'string'},
            'price_currency': {'type': 'string'},
            'compare_at_amount': {'type': 'string'},
            'variant_type': {
                'type': 'string',
                'enum': ['physical', 'digital', 'virtual'],
                'default': 'physical',
            },
            'requires_shipping': {
                'type': 'boolean',
                'description': 'Auto-defaults from variant_type when omitted.',
            },
            'is_taxable': {'type': 'boolean'},
            'inventory_policy': {'type': 'string', 'enum': ['deny', 'continue'], 'default': 'deny'},
            'barcode': {'type': 'string'},
            'is_active': {'type': 'boolean'},
            'sort_order': {'type': 'integer'},
        },
        'required': ['product_slug', 'name', 'sku'],
    },
)
def create_variant_tool(
    *,
    product_slug: str,
    name: str,
    sku: str,
    **fields,
) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, create_variant

    kwargs = {k: v for k, v in fields.items() if v not in (None, '')}
    try:
        r = create_variant(product_slug=product_slug, name=name, sku=sku, **kwargs)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(
        output=r,
        display=f'Created variant {r["name"]!r} ({r["sku"]}, {r["variant_type"]}) on {product_slug}',
    )


@tool(
    name='catalog.update_variant',
    description=(
        'Update an existing variant by SKU. Pass only the fields you '
        'want to change. To rename the SKU itself, pass a `new_sku` '
        '(NOT yet supported — use a delete + create for now).'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'sku': {'type': 'string'},
            'name': {'type': 'string'},
            'price_amount': {'type': 'string'},
            'price_currency': {'type': 'string'},
            'compare_at_amount': {'type': 'string'},
            'variant_type': {
                'type': 'string',
                'enum': ['physical', 'digital', 'audiobook', 'virtual'],
            },
            'requires_shipping': {'type': 'boolean'},
            'is_taxable': {'type': 'boolean'},
            'inventory_policy': {'type': 'string', 'enum': ['deny', 'continue']},
            'barcode': {'type': 'string'},
            'is_active': {'type': 'boolean'},
            'sort_order': {'type': 'integer'},
        },
        'required': ['sku'],
    },
)
def update_variant_tool(*, sku: str, **fields) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, update_variant

    _refuse_price_change(fields)
    kwargs = {k: v for k, v in fields.items() if v not in (None, '')}
    try:
        r = update_variant(sku=sku, **kwargs)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(output=r, display=f'Updated variant {r["sku"]}')


@tool(
    name='catalog.archive_category',
    description=(
        'Archive (delete) a category. Products in the category are detached '
        '(category=null) rather than cascade-deleted.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
    requires_approval=True,
)
def archive_category_tool(*, slug: str) -> ToolResult:
    from plugins.installed.catalog.services import PublishError, archive_category

    try:
        r = archive_category(slug=slug)
    except PublishError as e:
        raise ToolError(str(e)) from None
    return ToolResult(output=r, display=f'Archived category {r["slug"]}')
