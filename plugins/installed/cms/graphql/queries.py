"""CMS GraphQL — read + write access to Pages and Blocks.

Registered via ``register_graphql_extension`` in ``cms/app.py``; the schema
builder (``api/schema.py``) merges any ``*QueryExtension`` / ``*MutationExtension``
classes it finds into the root schema.

Gated with the ``cms.read`` / ``cms.write`` scopes (see
``api.graphql_permissions``): staff/superuser sessions, API keys carrying the
scope, and agents with the scope (or ``admin``) all pass. ``Page.body`` is
bleach-sanitised on save by the model, so HTML written here is safe — the same
contract as the dashboard editor and the MCP tools.
"""

# ruff: noqa: PLC0415, UP006, UP035, UP045 — lazy model imports; List/Optional matches the affiliates GraphQL pattern Strawberry resolves.
from __future__ import annotations

from typing import List, Optional

import strawberry
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from strawberry.scalars import JSON

from api.graphql_permissions import require_scope

_STATES = {'draft', 'scheduled', 'published', 'archived'}
_LAYOUTS = {'default', 'long_form', 'landing'}


@strawberry.type
class CmsPageType:
    id: strawberry.ID
    slug: str
    title: str
    excerpt: str
    body: str
    state: str
    layout: str
    publish_at: Optional[str]
    metadata: JSON
    updated_at: str


@strawberry.type
class CmsJournalEntryType:
    slug: str
    title: str
    excerpt: str
    body: str
    published_at: Optional[str]
    updated_at: Optional[str]
    image: str
    author: str


def _page_type(p) -> CmsPageType:
    return CmsPageType(
        id=str(p.id),
        slug=p.slug,
        title=p.title,
        excerpt=p.excerpt,
        body=p.body,
        state=p.state,
        layout=p.layout,
        publish_at=p.publish_at.isoformat() if p.publish_at else None,
        metadata=dict(p.metadata or {}),
        updated_at=p.updated_at.isoformat(),
    )


def _journal_entry_type(entry: dict) -> CmsJournalEntryType:
    published_at = entry.get('published_at')
    updated_at = entry.get('updated_at')
    return CmsJournalEntryType(
        slug=entry.get('slug', ''),
        title=entry.get('title', ''),
        excerpt=entry.get('excerpt', ''),
        body=entry.get('body', ''),
        published_at=published_at.isoformat() if published_at else None,
        updated_at=updated_at.isoformat() if updated_at else None,
        image=entry.get('image', ''),
        author=entry.get('author', ''),
    )


@strawberry.type
class CmsQueryExtension:
    @strawberry.field(description='List CMS pages (newest first; optional state filter).')
    def cms_pages(self, info: strawberry.Info, state: Optional[str] = None) -> List[CmsPageType]:
        require_scope(info, 'cms.read')
        from plugins.installed.cms.models import Page

        qs = Page.objects.all().order_by('-updated_at')
        if state:
            qs = qs.filter(state=state)
        return [_page_type(p) for p in qs[:200]]

    @strawberry.field(description='Get one CMS page by slug (or null).')
    def cms_page(self, info: strawberry.Info, slug: str) -> Optional[CmsPageType]:
        require_scope(info, 'cms.read')
        from plugins.installed.cms.models import Page

        p = Page.objects.filter(slug=slug).first()
        return _page_type(p) if p else None

    @strawberry.field(description='List published journal entries from CMS pages.')
    def journal_entries(self, info: strawberry.Info, limit: int = 50) -> List[CmsJournalEntryType]:
        require_scope(info, 'cms.read')
        from plugins.installed.cms.services import list_journal_entries

        return [_journal_entry_type(entry) for entry in list_journal_entries(limit=limit)]

    @strawberry.field(description='Get one published journal entry by slug (or null).')
    def journal_entry(self, info: strawberry.Info, slug: str) -> Optional[CmsJournalEntryType]:
        require_scope(info, 'cms.read')
        from plugins.installed.cms.services import get_journal_entry

        entry = get_journal_entry(slug)
        return _journal_entry_type(entry) if entry else None


@strawberry.input
class CmsPageInput:
    title: Optional[str] = None
    slug: Optional[str] = None
    body: Optional[str] = None
    excerpt: Optional[str] = None
    state: Optional[str] = None
    layout: Optional[str] = None
    publish_at: Optional[str] = None
    metadata: Optional[JSON] = None


def _parsed_publish_at(raw_value: Optional[str]):
    if raw_value is None:
        return None
    raw_value = raw_value.strip()
    if not raw_value:
        return None
    parsed = parse_datetime(raw_value)
    if parsed is None:
        raise ValueError('publish_at must be a valid ISO-8601 datetime string.')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@strawberry.type
class CmsMutationExtension:
    @strawberry.mutation(description='Create a CMS page (slug auto-derives from the title).')
    def create_page(self, info: strawberry.Info, input: CmsPageInput) -> CmsPageType:
        require_scope(info, 'cms.write')
        from django.utils.text import slugify

        from plugins.installed.cms.models import Page

        title = (input.title or '').strip()
        slug = slugify(input.slug or title)[:200]
        if not title or not slug:
            raise ValueError('A page needs a title (the slug derives from it).')
        if Page.objects.filter(slug=slug).exists():
            raise ValueError(f'A page with slug "{slug}" already exists.')
        p = Page.objects.create(
            title=title[:200],
            slug=slug,
            body=input.body or '',
            excerpt=(input.excerpt or '')[:300],
            state=input.state if input.state in _STATES else 'draft',
            layout=input.layout if input.layout in _LAYOUTS else 'default',
            publish_at=_parsed_publish_at(input.publish_at),
            metadata=dict(input.metadata or {}),
        )
        return _page_type(p)

    @strawberry.mutation(description='Update a CMS page by slug — only provided fields change.')
    def update_page(self, info: strawberry.Info, slug: str, input: CmsPageInput) -> CmsPageType:
        require_scope(info, 'cms.write')
        from django.utils.text import slugify

        from plugins.installed.cms.models import Page

        p = Page.objects.filter(slug=slug).first()
        if not p:
            raise ValueError(f'No page with slug "{slug}".')
        if input.title is not None:
            p.title = input.title[:200]
        if input.body is not None:
            p.body = input.body
        if input.excerpt is not None:
            p.excerpt = input.excerpt[:300]
        if input.state is not None and input.state in _STATES:
            p.state = input.state
        if input.layout is not None and input.layout in _LAYOUTS:
            p.layout = input.layout
        if input.publish_at is not None:
            p.publish_at = _parsed_publish_at(input.publish_at)
        if input.metadata is not None:
            p.metadata = dict(input.metadata or {})
        if input.slug:
            new_slug = slugify(input.slug)[:200]
            if new_slug and new_slug != p.slug and not Page.objects.filter(slug=new_slug).exists():
                p.slug = new_slug
        p.save()
        return _page_type(p)

    @strawberry.mutation(description='Delete a CMS page by slug. Returns true if one was removed.')
    def delete_page(self, info: strawberry.Info, slug: str) -> bool:
        require_scope(info, 'cms.write')
        from plugins.installed.cms.models import Page

        count, _ = Page.objects.filter(slug=slug).delete()
        return count > 0

    @strawberry.mutation(description='Duplicate a CMS page (as a draft, slug "<slug>-copy").')
    def duplicate_page(self, info: strawberry.Info, slug: str) -> CmsPageType:
        require_scope(info, 'cms.write')
        from plugins.installed.cms.models import Page

        src = Page.objects.filter(slug=slug).first()
        if not src:
            raise ValueError(f'No page with slug "{slug}".')
        base = f'{src.slug}-copy'
        new_slug, n = base, 2
        while Page.objects.filter(slug=new_slug).exists():
            new_slug, n = f'{base}-{n}', n + 1
        dup = Page.objects.create(
            title=f'{src.title} (copy)',
            slug=new_slug,
            body=src.body,
            excerpt=src.excerpt,
            layout=src.layout,
            state='draft',
            metadata=dict(src.metadata or {}),
        )
        return _page_type(dup)

    @strawberry.mutation(description='Create or update a named CMS block. Returns the block key.')
    def upsert_block(
        self,
        info: strawberry.Info,
        key: str,
        label: str,
        body: str = '',
        kind: str = 'html',
    ) -> str:
        require_scope(info, 'cms.write')
        from plugins.installed.cms.models import Block

        block, _ = Block.objects.update_or_create(
            key=key,
            defaults={'label': label[:200], 'kind': kind, 'body': body, 'is_active': True},
        )
        return block.key
