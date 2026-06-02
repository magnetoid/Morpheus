"""CMS agent tools."""

# ruff: noqa: PLC0415 — model imports are lazy (load-order safe).
from __future__ import annotations

from django.utils.text import slugify

from core.agents import ToolError, ToolResult, tool


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
