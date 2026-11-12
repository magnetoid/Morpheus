"""SEO tools the agent layer can call."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


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
    return ToolResult(
        output={
            'slug': slug,
            'meta': {
                'title': meta.title,
                'description': meta.description,
                'keywords': meta.keywords,
            },
        }
    )


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
    *,
    slug: str,
    title: str = '',
    description: str = '',
    keywords: str = '',
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
        content_type=ct,
        object_id=str(product.id),
        defaults={
            'title': title[:200],
            # These clamps must match the COLUMN widths, not a guess: 500 into a
            # CharField(320) is a DataError on Postgres that sqlite silently
            # truncates, so local tests stayed green while prod raised.
            'description': description[:320],
            'focus_keyword': keywords[:120],
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
    # seo.write, not seo.read: this STORES the result (store_audit writes a
    # SeoAuditResult row), and a tool that writes must not be reachable with a
    # read scope.
    scopes=['seo.write'],
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
    return ToolResult(output={'slug': slug, **result}, display=f'{slug}: {result["score"]}/100')


@tool(
    name='seo.audit_all',
    description='Audit every active product. Returns count.',
    scopes=['seo.write'],
    schema={
        'type': 'object',
        'properties': {
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 1000, 'default': 200},
        },
    },
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
    schema={
        'type': 'object',
        'properties': {
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def list_404s_tool(*, limit: int = 25) -> ToolResult:
    # Reads only. It used to call refresh_404_suggestions(), which STORES a
    # suggested_target on every row it can match — a write reachable with a read
    # scope, and an expensive one (it loads every live slug). Suggestions are
    # refreshed from the 404 page's own button now.
    from plugins.installed.seo.models import NotFoundLog

    rows = list(
        NotFoundLog.objects.filter(is_resolved=False).order_by('-hit_count')[
            : max(1, min(int(limit or 25), 100))
        ]
    )
    return ToolResult(
        output={
            'count': len(rows),
            'paths': [
                {
                    'path': r.path,
                    'hits': r.hit_count,
                    'suggested_target': r.suggested_target,
                    'last_seen': r.last_seen_at.isoformat(),
                }
                for r in rows
            ],
        }
    )


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
        defaults={
            'to_path': to_path[:500],
            'status_code': 301,
            'is_active': True,
            'note': note[:200],
        },
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
    return ToolResult(
        output={'updated': n, 'skipped': skipped}, display=f'updated {n}, skipped {skipped}'
    )


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
            'slugs': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Optional list of product slugs to restrict to.',
            },
            'force': {
                'type': 'boolean',
                'default': False,
                'description': 'Overwrite existing Related-reading block.',
            },
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
    return ToolResult(
        output={'summary': summary, 'log_tail': out[-600:]},
        display=f'applied={summary.get("applied", 0)} skipped={summary.get("skipped", 0)}',
    )


@tool(
    name='seo.apply_external_links',
    description=(
        'Append a "Sources and references" section of VERIFIED external links to '
        'each active book description. Links are built ONLY from stored, '
        'reconciled identifiers (Open Library work id, OCLC, ISBN-13) plus the '
        "author's Wikipedia page confirmed via the Wikipedia API — never "
        'invented URLs. Idempotent: skips books already done. Returns counts.'
    ),
    scopes=['seo.write'],
    schema={
        'type': 'object',
        'properties': {
            'slugs': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Optional list of product slugs to restrict to.',
            },
            'verify_web': {
                'type': 'boolean',
                'default': True,
                'description': 'Also add the verified Wikipedia author link (needs outbound HTTPS).',
            },
            'force': {
                'type': 'boolean',
                'default': False,
                'description': 'Rebuild the references block even if already applied.',
            },
            'limit': {
                'type': 'integer',
                'default': 0,
                'description': 'Stop after N writes (0 = all).',
            },
        },
    },
    requires_approval=True,
)
def apply_external_links_tool(
    *,
    slugs: list[str] | None = None,
    verify_web: bool = True,
    force: bool = False,
    limit: int = 0,
) -> ToolResult:
    import re
    from io import StringIO

    from django.core.management import call_command

    buf = StringIO()
    kwargs = {'force': bool(force), 'limit': int(limit or 0), 'stdout': buf, 'stderr': buf}
    if not verify_web:
        kwargs['no_verify_web'] = True
    if slugs:
        kwargs['slugs'] = ','.join(s for s in slugs if s)
    call_command('apply_external_links', **kwargs)
    out = buf.getvalue()
    summary = {}
    for token in ('applied', 'skipped', 'no_links'):
        m = re.search(rf'{token}=(\d+)', out)
        if m:
            summary[token] = int(m.group(1))
    return ToolResult(
        output={'summary': summary, 'log_tail': out[-600:]},
        display=f'applied={summary.get("applied", 0)} skipped={summary.get("skipped", 0)}',
    )


# ── Sitemap (migrated from core/assistant/tools/admin_ops.py, arch-debt refactor).
#    Was defined in core but never surfaced in get_default_tools(); now a proper,
#    disable-safe seo agent tool (registry-contributed, seo-scoped). ────────────
@tool(
    name='seo.regenerate_sitemap',
    description=(
        'Regenerate the sitemap: recount every URL, purge the CDN copies of the '
        'sitemap files, and ping IndexNow so crawlers re-fetch. Safe + idempotent '
        '— run whenever pages/products/taxonomies were added or changed.'
    ),
    scopes=['system.write'],
    schema={'type': 'object', 'properties': {}},
)
def seo_regenerate_sitemap_tool() -> ToolResult:
    from plugins.installed.seo.services import regenerate_sitemap

    res = regenerate_sitemap(triggered_by='linda')
    counts = res.get('counts') or {}
    return ToolResult(
        output=res,
        display=(
            f'Sitemap regenerated: {counts.get("total", 0)} URLs, '
            f'{"edge cache purge requested, " if res.get("purged") else ""}'
            f'ping {"sent" if res.get("pinged") else "skipped"}.'
        ),
    )


def _plain(value):
    """A report value Linda can read as JSON (dates as text, money as amount and currency)."""
    from datetime import date  # noqa: PLC0415

    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, 'amount') and hasattr(value, 'currency'):
        return {'amount': str(value.amount), 'currency': str(value.currency)}
    return value


@tool(
    name='seo.search_performance',
    description=(
        'Google search numbers from Search Console over the last N days Google has '
        'settled: clicks, impressions, click-through rate and average position, against '
        'the N days before, and the top queries or pages. A page row also carries the '
        "visits Google's results sent to it and their net sales. The totals and queries "
        "are the whole property's (a domain property's count its other subdomains too); "
        "pages are this store's only. Says when Search Console is not connected."
    ),
    scopes=['seo.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 486, 'default': 28},
            'by': {'type': 'string', 'enum': ['query', 'page'], 'default': 'query'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def search_performance_tool(*, days: int = 28, by: str = 'query', limit: int = 25) -> ToolResult:
    from plugins.installed.seo import search_console

    state = search_console.key_state()
    out = _plain(search_console.report(days=days, by=by, limit=min(int(limit or 25), 100)))
    out['connected'] = state == 'ok'
    if state != 'ok':
        out['note'] = (
            'Search Console is not connected: paste a service account key on Settings → SEO '
            'and add its email as a user of the property in Search Console.'
        )
    last = search_console.last_pull()
    if last and not last.get('ok'):
        out['last_fetch_error'] = last.get('detail', '')
    return ToolResult(output=out)


@tool(
    name='seo.inspect_url',
    description=(
        "Ask Google how it sees one of the store's pages (Search Console URL inspection): "
        'verdict, coverage, whether indexing is allowed, robots.txt, the last fetch and '
        "Google's chosen canonical against the page's own. Takes a path or a full address "
        'on this store.'
    ),
    scopes=['seo.read'],
    schema={
        'type': 'object',
        'properties': {
            'url': {'type': 'string', 'description': 'A path (/products/x/) or full URL.'}
        },
        'required': ['url'],
    },
)
def inspect_url_tool(*, url: str) -> ToolResult:
    from plugins.installed.seo import search_console

    try:
        return ToolResult(output=search_console.inspect_url(url))
    except search_console.SearchConsoleError as e:
        raise ToolError(str(e)) from e


# ─────────────────────────────────────────────────────────────────────────────
# Structured-data editor (SEO → Structured data): the blocks a merchant adds to
# one page's graph — FAQ, recipe, video, course or a custom type (v0.163.0).
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA_TARGET = {
    'model': {
        'type': 'string',
        'description': "The object's kind as app.model, e.g. catalog.product or cms.page.",
    },
    'object_id': {'type': 'string', 'description': "The object's id, or its slug."},
}


def _schema_target(model: str, object_id: str):
    from django.contrib.contenttypes.models import ContentType

    app_label, _, name = (model or '').lower().partition('.')
    ct = ContentType.objects.filter(app_label=app_label, model=name).first()
    if ct is None or ct.model_class() is None:
        raise ToolError(f'Unknown kind of object: {model}')
    cls = ct.model_class()
    obj = None
    try:
        obj = cls.objects.filter(pk=object_id).first()
    except Exception:  # noqa: BLE001 — a slug is not a valid pk (UUID, int)
        obj = None
    if obj is None and any(f.name == 'slug' for f in cls._meta.get_fields()):
        obj = cls.objects.filter(slug=object_id).first()
    if obj is None:
        raise ToolError(f'No {model} {object_id}.')
    return ct, obj


def _schema_rows(entries: list) -> list[dict]:
    from plugins.installed.seo.schema_types import block_type, refusal

    return [
        {
            'index': index,
            'type': block_type(entry),
            'data': (entry.get('data') if isinstance(entry, dict) else None) or {},
            'shows': not refusal(entry),
            **({'why_not': refusal(entry)} if refusal(entry) else {}),
        }
        for index, entry in enumerate(entries or [])
    ]


@tool(
    name='seo.schema_blocks',
    description=(
        'The structured-data blocks the merchant added to pages (SEO → Structured data): '
        'FAQ, recipe, video, course or a custom schema.org type. With model and object_id, '
        "one object's blocks (with each block's index and whether it shows) and the types "
        'that can be added; without, every object that has blocks.'
    ),
    scopes=['seo.read'],
    schema={'type': 'object', 'properties': dict(_SCHEMA_TARGET)},
)
def schema_blocks_tool(*, model: str = '', object_id: str = '') -> ToolResult:
    from plugins.installed.seo.models import SeoMeta
    from plugins.installed.seo.schema_types import SCHEMA_TYPES

    types = [{'type': t['key'], 'label': t['label'], 'fields': t['fields']} for t in SCHEMA_TYPES]
    if model and object_id:
        ct, obj = _schema_target(model, object_id)
        meta = SeoMeta.objects.filter(content_type=ct, object_id=str(obj.pk)).first()
        return ToolResult(
            output={
                'object': str(obj),
                'blocks': _schema_rows(meta.schema_blocks if meta else []),
                'types': types,
            }
        )
    rows = []
    for meta in SeoMeta.objects.exclude(schema_blocks=[]).select_related('content_type')[:50]:
        if not meta.schema_blocks:
            continue
        ct = meta.content_type
        rows.append(
            {
                'model': f'{ct.app_label}.{ct.model}',
                'object_id': meta.object_id,
                'blocks': _schema_rows(meta.schema_blocks),
            }
        )
    return ToolResult(output={'objects': rows, 'types': types})


@tool(
    name='seo.set_schema_block',
    description=(
        "Add a structured-data block to one object's page, or replace the block at index. "
        'type is FAQPage, Recipe, VideoObject, Course or Custom; data holds the fields '
        'seo.schema_blocks lists for that type (an FAQ: {"items": [{"question", "answer"}]}). '
        'A type the store writes itself (Product, Organization, Article, Event, …) is refused.'
    ),
    scopes=['seo.write'],
    schema={
        'type': 'object',
        'properties': {
            **_SCHEMA_TARGET,
            'type': {'type': 'string'},
            'data': {'type': 'object'},
            'index': {'type': 'integer', 'description': 'Replace this block instead of adding.'},
        },
        'required': ['model', 'object_id', 'type', 'data'],
    },
    requires_approval=True,
)
def set_schema_block_tool(
    *, model: str, object_id: str, type: str, data: dict, index: int | None = None
) -> ToolResult:
    from plugins.installed.seo.models import SeoMeta
    from plugins.installed.seo.schema_types import build_block, refusal

    entry = {'type': type, 'data': data if isinstance(data, dict) else {}}
    if reason := refusal(entry):
        raise ToolError(reason)
    if not build_block(entry['type'], entry['data']):
        raise ToolError('The block has nothing in it: fill its required fields.')
    ct, obj = _schema_target(model, object_id)
    meta, _ = SeoMeta.objects.get_or_create(content_type=ct, object_id=str(obj.pk))
    blocks = list(meta.schema_blocks or [])
    if index is None:
        blocks.append(entry)
    elif 0 <= index < len(blocks):
        blocks[index] = entry
    else:
        raise ToolError(f'There is no block {index}.')
    meta.schema_blocks = blocks
    meta.save()
    return ToolResult(
        output={'object': str(obj), 'blocks': _schema_rows(blocks)},
        display=f'Saved a {type} block on {obj}',
    )


@tool(
    name='seo.delete_schema_block',
    description="Delete the structured-data block at index from one object's page.",
    scopes=['seo.write'],
    schema={
        'type': 'object',
        'properties': {**_SCHEMA_TARGET, 'index': {'type': 'integer'}},
        'required': ['model', 'object_id', 'index'],
    },
    requires_approval=True,
)
def delete_schema_block_tool(*, model: str, object_id: str, index: int) -> ToolResult:
    from plugins.installed.seo.models import SeoMeta

    ct, obj = _schema_target(model, object_id)
    meta = SeoMeta.objects.filter(content_type=ct, object_id=str(obj.pk)).first()
    blocks = list(meta.schema_blocks or []) if meta else []
    if not 0 <= index < len(blocks):
        raise ToolError(f'There is no block {index}.')
    removed = blocks.pop(index)
    meta.schema_blocks = blocks
    meta.save()
    return ToolResult(
        output={'object': str(obj), 'blocks': _schema_rows(blocks)},
        display=f'Deleted a {removed.get("type", "")} block from {obj}',
    )
