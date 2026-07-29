"""CMS agent tools."""

# ruff: noqa: PLC0415 — model imports are lazy (load-order safe).
from __future__ import annotations

from django.utils.text import slugify

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='cms.create_page',
    description='Create a new CMS page. Slug auto-derived from title if not provided.',
    scopes=['cms.write'],
    schema={
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'body': {'type': 'string', 'description': 'Markdown / HTML.'},
            'slug': {'type': 'string'},
            'state': {'type': 'string', 'enum': ['draft', 'published'], 'default': 'draft'},
            'excerpt': {'type': 'string'},
        },
        'required': ['title', 'body'],
    },
    requires_approval=True,
)
def create_page_tool(
    *, title: str, body: str, slug: str = '', state: str = 'draft', excerpt: str = ''
) -> ToolResult:
    from plugins.installed.cms.models import Page

    page = Page.objects.create(
        slug=slug or slugify(title)[:200],
        title=title[:200],
        body=body,
        state=state,
        excerpt=excerpt[:300],
    )
    return ToolResult(
        output={'id': str(page.id), 'slug': page.slug, 'state': page.state},
        display=f'Created page /p/{page.slug}/ ({state})',
    )


@tool(
    name='cms.list_pages',
    description='List CMS pages.',
    scopes=['cms.read'],
    schema={
        'type': 'object',
        'properties': {
            'state': {'type': 'string', 'enum': ['draft', 'scheduled', 'published', 'archived']},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def list_pages_tool(*, state: str = '', limit: int = 25) -> ToolResult:
    from plugins.installed.cms.models import Page

    qs = Page.objects.all().order_by('-updated_at')
    if state:
        qs = qs.filter(state=state)
    rows = list(qs[: max(1, min(int(limit or 25), 100))])
    return ToolResult(
        output={
            'pages': [
                {
                    'slug': p.slug,
                    'title': p.title,
                    'state': p.state,
                    'updated_at': p.updated_at.isoformat(),
                }
                for p in rows
            ],
        }
    )


@tool(
    name='cms.upsert_block',
    description='Create or update a named CMS block (banner / callout / CTA).',
    scopes=['cms.write'],
    schema={
        'type': 'object',
        'properties': {
            'key': {'type': 'string'},
            'label': {'type': 'string'},
            'kind': {'type': 'string', 'enum': ['html', 'image', 'callout', 'cta', 'embed']},
            'body': {'type': 'string'},
            'cta_label': {'type': 'string'},
            'cta_url': {'type': 'string'},
            'image_url': {'type': 'string'},
        },
        'required': ['key', 'label'],
    },
    requires_approval=True,
)
def upsert_block_tool(
    *,
    key: str,
    label: str,
    kind: str = 'html',
    body: str = '',
    cta_label: str = '',
    cta_url: str = '',
    image_url: str = '',
) -> ToolResult:
    from plugins.installed.cms.models import Block

    block, created = Block.objects.update_or_create(
        key=key,
        defaults={
            'label': label[:200],
            'kind': kind,
            'body': body,
            'cta_label': cta_label[:100],
            'cta_url': cta_url[:500],
            'image_url': image_url[:600],
            'is_active': True,
        },
    )
    return ToolResult(
        output={'key': block.key, 'created': created},
        display=f'{"Created" if created else "Updated"} block "{block.key}"',
    )


@tool(
    name='cms.recent_form_submissions',
    description='List recent submissions across all CMS forms.',
    scopes=['cms.read'],
    schema={
        'type': 'object',
        'properties': {
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def recent_submissions_tool(*, limit: int = 25) -> ToolResult:
    from plugins.installed.cms.models import FormSubmission

    rows = list(
        FormSubmission.objects.select_related('form').order_by('-created_at')[
            : max(1, min(int(limit or 25), 100))
        ]
    )
    return ToolResult(
        output={
            'submissions': [
                {
                    'form': r.form.key,
                    'email': r.submitter_email,
                    'when': r.created_at.isoformat(),
                    'fields': list((r.payload or {}).keys()),
                }
                for r in rows
            ],
        }
    )


@tool(
    name='cms.get_page',
    description='Get one CMS page by slug, including its full body.',
    scopes=['cms.read'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
)
def get_page_tool(*, slug: str) -> ToolResult:
    from plugins.installed.cms.models import Page

    page = Page.objects.filter(slug=slug).first()
    if page is None:
        raise ToolError(f'No CMS page with slug "{slug}".')
    return ToolResult(
        output={
            'slug': page.slug,
            'title': page.title,
            'state': page.state,
            'layout': page.layout,
            'excerpt': page.excerpt,
            'body': page.body,
            'updated_at': page.updated_at.isoformat(),
        }
    )


@tool(
    name='cms.update_page',
    description='Update an existing CMS page (by slug). Only the fields you pass change.',
    scopes=['cms.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string', 'description': 'Slug of the page to update.'},
            'title': {'type': 'string'},
            'body': {'type': 'string', 'description': 'Markdown / HTML.'},
            'excerpt': {'type': 'string'},
            'state': {'type': 'string', 'enum': ['draft', 'scheduled', 'published', 'archived']},
            'layout': {'type': 'string', 'enum': ['default', 'long_form', 'landing']},
        },
        'required': ['slug'],
    },
    requires_approval=True,
)
def update_page_tool(
    *,
    slug: str,
    title: str | None = None,
    body: str | None = None,
    excerpt: str | None = None,
    state: str | None = None,
    layout: str | None = None,
) -> ToolResult:
    from plugins.installed.cms.models import Page

    page = Page.objects.filter(slug=slug).first()
    if page is None:
        raise ToolError(f'No CMS page with slug "{slug}".')
    if title is not None:
        page.title = title[:200]
    if body is not None:
        page.body = body
    if excerpt is not None:
        page.excerpt = excerpt[:300]
    if state in ('draft', 'scheduled', 'published', 'archived'):
        page.state = state
    if layout in ('default', 'long_form', 'landing'):
        page.layout = layout
    page.save()
    return ToolResult(
        output={'slug': page.slug, 'state': page.state}, display=f'Updated page /p/{page.slug}/'
    )


@tool(
    name='cms.delete_page',
    description='Delete a CMS page by slug. Cannot be undone.',
    scopes=['cms.write'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
    requires_approval=True,
)
def delete_page_tool(*, slug: str) -> ToolResult:
    from plugins.installed.cms.models import Page

    page = Page.objects.filter(slug=slug).first()
    if page is None:
        raise ToolError(f'No CMS page with slug "{slug}".')
    title = page.title
    page.delete()
    return ToolResult(output={'deleted': slug}, display=f'Deleted page "{title}"')


@tool(
    name='cms.pages',
    description='List CMS pages with title, slug, state, and updated date.',
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'state': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 50},
        },
    },
)
def cms_pages_tool(*, state: str = '', limit: int = 50) -> ToolResult:
    from plugins.installed.cms.models import Page

    qs = Page.objects.all()
    if state:
        qs = qs.filter(state=state)
    qs = qs.order_by('-updated_at')[: max(1, min(int(limit or 50), 100))]
    rows = [
        {
            'id': str(p.pk),
            'title': getattr(p, 'title', ''),
            'slug': getattr(p, 'slug', ''),
            'state': getattr(p, 'state', ''),
            'updated_at': p.updated_at.isoformat() if getattr(p, 'updated_at', None) else '',
            'published_at': (
                p.published_at.isoformat() if getattr(p, 'published_at', None) else ''
            ),
        }
        for p in qs
    ]
    return ToolResult(output={'pages': rows, 'count': len(rows)}, display=f'{len(rows)} page(s)')


@tool(
    name='email.templates',
    description=(
        'List email templates: key, subject, whether the merchant has '
        'customised the default. Read-only — does not return body HTML '
        'because it can be very long; use db.find on EmailTemplate for '
        'a single full record.'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def email_templates_tool() -> ToolResult:
    from plugins.installed.cms.models import EmailTemplate

    rows = [
        {
            'key': getattr(t, 'key', ''),
            'subject': getattr(t, 'subject', ''),
            'is_customised': bool(getattr(t, 'is_customised', False)),
            'updated_at': t.updated_at.isoformat() if getattr(t, 'updated_at', None) else '',
        }
        for t in EmailTemplate.objects.all().order_by('key')
    ]
    return ToolResult(output={'templates': rows, 'count': len(rows)})


# ── Publish / unpublish (migrated from core/assistant/tools/ecommerce_writes.py,
#    arch-debt refactor) ─────────────────────────────────────────────────────
# Names unchanged — Linda sources them by name (get_default_tools._migrated_names).
# Staged-mode + confirm helpers stay core (plugin -> core is the right direction).


@tool(
    name='cms.publish_page',
    description=(
        'Publish a CMS page (sets state=published). Pass `id` or `slug`. Requires `confirmed=True`.'
    ),
    scopes=['content.write'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'slug': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
    },
    requires_approval=True,
)
def cms_publish_page_tool(
    *, id: str = '', slug: str = '', confirmed: bool = False, context: dict | None = None
) -> ToolResult:
    from core.assistant.tools.ecommerce_writes import (
        _is_staged,
        _obj_ref,
        _require_confirmed,
        _stage,
    )

    staged = _is_staged(context)
    if not staged:
        _require_confirmed(confirmed)
    try:
        from django.utils import timezone

        from plugins.installed.cms.models import Page
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'cms plugin unavailable: {e}') from e
    p = None
    if id:
        p = Page.objects.filter(pk=id).first()
    if p is None and slug:
        p = Page.objects.filter(slug=slug).first()
    if p is None:
        raise ToolError('page not found — pass id or slug')
    prev = getattr(p, 'state', '')
    if staged:
        title = getattr(p, 'title', '') or str(p.pk)
        return _stage(
            context=context,
            tool_name='cms.publish_page',
            kind='cms.publish',
            title=f'Publish page "{title}"',
            summary=f"Set page {title!r} state from {prev!r} to 'published'.",
            changes=[{'object': _obj_ref(p), 'field': 'state', 'old': prev, 'new': 'published'}],
            target=p,
        )
    p.state = 'published'
    if hasattr(p, 'published_at') and not getattr(p, 'published_at', None):
        p.published_at = timezone.now()
        p.save(
            update_fields=['state', 'published_at', 'updated_at']
            if hasattr(p, 'updated_at')
            else ['state', 'published_at']
        )
    else:
        p.save(update_fields=['state', 'updated_at'] if hasattr(p, 'updated_at') else ['state'])
    return ToolResult(
        output={
            'page_id': str(p.pk),
            'slug': getattr(p, 'slug', ''),
            'previous_state': prev,
            'new_state': 'published',
        },
        display=f'published "{getattr(p, "title", p.pk)}"',
    )


@tool(
    name='cms.unpublish_page',
    description=(
        'Unpublish a CMS page (sets state=draft). Pass `id` or `slug`. Requires `confirmed=True`.'
    ),
    scopes=['content.write'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'slug': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
    },
    requires_approval=True,
)
def cms_unpublish_page_tool(
    *, id: str = '', slug: str = '', confirmed: bool = False, context: dict | None = None
) -> ToolResult:
    from core.assistant.tools.ecommerce_writes import (
        _is_staged,
        _obj_ref,
        _require_confirmed,
        _stage,
    )

    staged = _is_staged(context)
    if not staged:
        _require_confirmed(confirmed)
    try:
        from plugins.installed.cms.models import Page
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'cms plugin unavailable: {e}') from e
    p = None
    if id:
        p = Page.objects.filter(pk=id).first()
    if p is None and slug:
        p = Page.objects.filter(slug=slug).first()
    if p is None:
        raise ToolError('page not found — pass id or slug')
    prev = getattr(p, 'state', '')
    if staged:
        title = getattr(p, 'title', '') or str(p.pk)
        return _stage(
            context=context,
            tool_name='cms.unpublish_page',
            kind='cms.unpublish',
            title=f'Unpublish page "{title}"',
            summary=f"Set page {title!r} state from {prev!r} to 'draft'.",
            changes=[{'object': _obj_ref(p), 'field': 'state', 'old': prev, 'new': 'draft'}],
            target=p,
        )
    p.state = 'draft'
    p.save(update_fields=['state', 'updated_at'] if hasattr(p, 'updated_at') else ['state'])
    return ToolResult(
        output={
            'page_id': str(p.pk),
            'slug': getattr(p, 'slug', ''),
            'previous_state': prev,
            'new_state': 'draft',
        },
        display=f'unpublished "{getattr(p, "title", p.pk)}"',
    )
