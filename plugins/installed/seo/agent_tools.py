"""SEO tools the agent layer can call."""
from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


@tool(
    name='seo.get_meta',
    description='Read SEO meta (title/description/keywords) for a product by slug.',
    scopes=['seo.read'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
)
def get_meta_tool(*, slug: str) -> ToolResult:
    from django.contrib.contenttypes.models import ContentType
    from plugins.installed.catalog.models import Product
    from plugins.installed.seo.models import SeoMeta

    try:
        product = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    ct = ContentType.objects.get_for_model(Product)
    try:
        meta = SeoMeta.objects.get(content_type=ct, object_id=str(product.id))
    except SeoMeta.DoesNotExist:
        return ToolResult(output={'slug': slug, 'meta': None})
    return ToolResult(output={
        'slug': slug,
        'meta': {
            'title': meta.title,
            'description': meta.description,
            'keywords': meta.keywords,
        },
    })


@tool(
    name='seo.set_meta',
    description='Set SEO meta (title/description/keywords) for a product by slug. Empty string clears a field.',
    scopes=['seo.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'title': {'type': 'string'},
            'description': {'type': 'string'},
            'keywords': {'type': 'string'},
        },
        'required': ['slug'],
    },
    requires_approval=True,
)
def set_meta_tool(
    *, slug: str, title: str = '', description: str = '', keywords: str = '',
) -> ToolResult:
    from django.contrib.contenttypes.models import ContentType
    from plugins.installed.catalog.models import Product
    from plugins.installed.seo.models import SeoMeta

    try:
        product = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    ct = ContentType.objects.get_for_model(Product)
    meta, _ = SeoMeta.objects.update_or_create(
        content_type=ct, object_id=str(product.id),
        defaults={
            'title': title[:200],
            'description': description[:500],
            'keywords': keywords[:300],
        },
    )
    return ToolResult(
        output={'slug': slug, 'title': meta.title, 'description': meta.description},
        display=f'Updated SEO meta for {slug}',
    )


# ─────────────────────────────────────────────────────────────────────────────
# Deep-SEO agent tools
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name='seo.audit_product',
    description='Run an SEO audit on a single product (by slug). Returns score + issues.',
    scopes=['seo.read'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
)
def audit_product_tool(*, slug: str) -> ToolResult:
    from plugins.installed.catalog.models import Product
    from plugins.installed.seo.services import audit_product, store_audit
    try:
        p = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    result = audit_product(p)
    store_audit(p, result)
    return ToolResult(output={'slug': slug, **result},
                      display=f'{slug}: {result["score"]}/100')


@tool(
    name='seo.audit_all',
    description='Audit every active product. Returns count.',
    scopes=['seo.write'],
    schema={'type': 'object', 'properties': {
        'limit': {'type': 'integer', 'minimum': 1, 'maximum': 1000, 'default': 200},
    }},
    requires_approval=True,
)
def audit_all_tool(*, limit: int = 200) -> ToolResult:
    from plugins.installed.seo.services import audit_all_products
    n = audit_all_products(limit=int(limit or 200))
    return ToolResult(output={'audited': n}, display=f'audited {n} products')


@tool(
    name='seo.list_404s',
    description='Top unresolved 404 paths with hit counts and suggested redirects.',
    scopes=['seo.read'],
    schema={'type': 'object', 'properties': {
        'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
    }},
)
def list_404s_tool(*, limit: int = 25) -> ToolResult:
    from plugins.installed.seo.models import NotFoundLog
    from plugins.installed.seo.services import refresh_404_suggestions
    refresh_404_suggestions()
    rows = list(NotFoundLog.objects.filter(is_resolved=False).order_by('-hit_count')[: max(1, min(int(limit or 25), 100))])
    return ToolResult(output={
        'count': len(rows),
        'paths': [
            {'path': r.path, 'hits': r.hit_count,
             'suggested_target': r.suggested_target,
             'last_seen': r.last_seen_at.isoformat()}
            for r in rows
        ],
    })


@tool(
    name='seo.create_redirect',
    description='Create a 301 redirect from a path to a target.',
    scopes=['seo.write'],
    schema={
        'type': 'object',
        'properties': {
            'from_path': {'type': 'string'},
            'to_path': {'type': 'string'},
            'note': {'type': 'string'},
        },
        'required': ['from_path', 'to_path'],
    },
    requires_approval=True,
)
def create_redirect_tool(*, from_path: str, to_path: str, note: str = '') -> ToolResult:
    from plugins.installed.seo.models import Redirect
    r, created = Redirect.objects.update_or_create(
        from_path=from_path[:500],
        defaults={'to_path': to_path[:500], 'status_code': 301,
                  'is_active': True, 'note': note[:200]},
    )
    return ToolResult(
        output={'from': r.from_path, 'to': r.to_path, 'created': created},
        display=f'{r.from_path} → {r.to_path}',
    )


@tool(
    name='seo.bulk_set_meta',
    description='Bulk-set SEO title and/or description for multiple products by slug.',
    scopes=['seo.write'],
    schema={
        'type': 'object',
        'properties': {
            'updates': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'slug': {'type': 'string'},
                        'title': {'type': 'string'},
                        'description': {'type': 'string'},
                    },
                    'required': ['slug'],
                },
                'description': 'List of {slug, title?, description?} entries.',
            },
        },
        'required': ['updates'],
    },
    requires_approval=True,
)
def bulk_set_meta_tool(*, updates: list[dict]) -> ToolResult:
    from django.contrib.contenttypes.models import ContentType
    from plugins.installed.catalog.models import Product
    from plugins.installed.seo.models import SeoMeta

    ct = ContentType.objects.get_for_model(Product)
    n = 0
    skipped = 0
    for upd in updates or []:
        slug = (upd.get('slug') or '').strip()
        if not slug:
            skipped += 1
            continue
        try:
            p = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            skipped += 1
            continue
        meta, _ = SeoMeta.objects.get_or_create(content_type=ct, object_id=str(p.pk))
        if 'title' in upd:
            meta.title = (upd.get('title') or '')[:200]
        if 'description' in upd:
            meta.description = (upd.get('description') or '')[:320]
        meta.auto_filled = False
        meta.save()
        n += 1
    return ToolResult(output={'updated': n, 'skipped': skipped},
                      display=f'updated {n}, skipped {skipped}')


@tool(
    name='seo.set_site_settings',
    description='Update site-wide SEO settings (organization name, social profiles, verification metas, etc.).',
    scopes=['seo.write'],
    schema={
        'type': 'object',
        'properties': {
            'organization_name': {'type': 'string'},
            'twitter_handle': {'type': 'string'},
            'default_og_image': {'type': 'string'},
            'google_site_verification': {'type': 'string'},
            'facebook_url': {'type': 'string'},
            'instagram_url': {'type': 'string'},
            'linkedin_url': {'type': 'string'},
        },
    },
    requires_approval=True,
)
def set_site_settings_tool(**kwargs) -> ToolResult:
    from plugins.installed.seo.services import site_settings
    s = site_settings()
    changed = []
    for field, val in kwargs.items():
        if val is None:
            continue
        if hasattr(s, field):
            setattr(s, field, str(val)[:600])
            changed.append(field)
    s.save()
    return ToolResult(output={'changed': changed}, display=f'updated {len(changed)} field(s)')


@tool(
    name='seo.apply_internal_links',
    description=(
        'Append a "Related reading" section with 1-3 internal links to '
        'every active product whose description has no links yet. Uses '
        'the recommendation graph to pick semantically-similar siblings. '
        'Idempotent: skips products already linked. Returns counts.'
    ),
    scopes=['seo.write'],
    schema={
        'type': 'object',
        'properties': {
            'slugs': {'type': 'array', 'items': {'type': 'string'},
                      'description': 'Optional list of product slugs to restrict to.'},
            'force': {'type': 'boolean', 'default': False,
                      'description': 'Overwrite existing Related-reading block.'},
        },
    },
    requires_approval=True,
)
def apply_internal_links_tool(*, slugs: list[str] | None = None, force: bool = False) -> ToolResult:
    from io import StringIO
    from django.core.management import call_command
    buf = StringIO()
    kwargs = {'force': bool(force), 'stdout': buf, 'stderr': buf}
    if slugs:
        kwargs['slugs'] = ','.join(s for s in slugs if s)
    call_command('apply_internal_links', **kwargs)
    out = buf.getvalue()
    # Parse the "done — applied=X skipped=Y no_suggestions=Z" tail line.
    summary = {}
    for token in ('applied', 'skipped', 'no_suggestions'):
        import re
        m = re.search(rf'{token}=(\d+)', out)
        if m:
            summary[token] = int(m.group(1))
    return ToolResult(output={'summary': summary, 'log_tail': out[-600:]},
                      display=f'applied={summary.get("applied", 0)} skipped={summary.get("skipped", 0)}')
