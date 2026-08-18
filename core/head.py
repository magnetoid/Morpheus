"""The document head as data — core's SEO seam.

**Why this exists.** Until v0.46 the storefront `<head>` was assembled by ~107
`{% seo_* %}` calls spread across 60 theme templates, so SEO was a property of
*the theme* rather than of the platform: a different theme — or the shipped
default `storefront/base.html` — emitted no canonical, no robots, no Open Graph
and no JSON-LD, and no plugin could contribute a single tag without owning a
whole `global_head` block.

Now the head is a **document**: core seeds it with a title and description, fires
`STOREFRONT_HEAD` as a filter, and whoever answers (the `seo` app, normally)
fills in the rest. A theme calls `{% storefront_head %}` once and gets everything;
a theme that never calls it still renders, just without the extras. Core defines
the shape and fires the event; it knows nothing about SEO rules (ADR 0017).

The document is *keyed*, not a string: every entry has a stable key
(``meta:description``, ``link:canonical``, ``jsonld:graph``) so a later handler
replaces an earlier one instead of emitting a duplicate — the failure mode this
replaces, where the theme and a page template each emitted their own `og:type`
and the page ended up with two.

Rendering is deterministic (title, metas, links, JSON-LD, raw) so a golden
snapshot of the output is a usable regression test.
"""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass, field
from html import escape

# Order the head is emitted in. Stable output keeps the parity snapshots
# meaningful and puts the title first, where a human reading `view-source`
# expects it.
_SECTION_ORDER = ('title', 'meta', 'link', 'jsonld', 'raw')

# `</script>` inside a JSON string would end the script element early and turn
# the rest of the page into executable markup — the one escape a JSON-LD
# serialiser must never skip.
_JSONLD_ESCAPES = (('<', '\\u003C'), ('>', '\\u003E'), ('&', '\\u0026'))


@dataclass(slots=True)
class HeadEntry:
    """One renderable thing in the head."""

    section: str  # 'title' | 'meta' | 'link' | 'jsonld' | 'raw'
    key: str  # stable identity; a later set() with the same key replaces
    attrs: dict[str, str] = field(default_factory=dict)
    content: str = ''
    source: str = ''  # who set it — surfaced in debugging/inspector, not HTML
    order: int = 100


class HeadDocument:
    """A mutable, keyed description of a page's `<head>`.

    Handlers mutate it through the small API below; nobody concatenates HTML.
    That is what makes "the theme sets a fallback title, the SEO app overrides
    it" a *replacement* rather than two `<title>` elements.
    """

    def __init__(self, *, path: str = '', language: str = '', source: str = 'core') -> None:
        self.path = path
        self.language = language
        self._entries: dict[str, HeadEntry] = {}
        self._default_source = source
        self.notes: list[str] = []  # human-readable decisions, for the inspector

    # -- writing ---------------------------------------------------------
    def set_title(self, title: str, *, source: str = '', order: int = 0) -> None:
        self._put(
            HeadEntry(
                section='title',
                key='title',
                content=(title or '').strip(),
                source=source or self._default_source,
                order=order,
            )
        )

    def meta(
        self,
        content: str,
        *,
        name: str = '',
        property: str = '',  # noqa: A002 — mirrors the HTML attribute name
        key: str = '',
        source: str = '',
        order: int = 100,
    ) -> None:
        """Add/replace a `<meta>`. Empty content removes the entry.

        Removal-on-empty matters: a handler that resolves "no description" must
        be able to clear a fallback the shell already set, rather than emit
        `<meta name="description" content="">`.
        """
        attr_name = 'name' if name else 'property'
        attr_value = name or property
        if not attr_value:
            return
        entry_key = key or f'meta:{attr_value}'
        if not (content or '').strip():
            self._entries.pop(entry_key, None)
            return
        self._put(
            HeadEntry(
                section='meta',
                key=entry_key,
                attrs={attr_name: attr_value, 'content': content.strip()},
                source=source or self._default_source,
                order=order,
            )
        )

    def link(
        self,
        rel: str,
        href: str,
        *,
        key: str = '',
        source: str = '',
        order: int = 100,
        **attrs: str,
    ) -> None:
        """Add/replace a `<link>`. Empty href removes the entry."""
        if not rel:
            return
        # Alternates are per (rel, hreflang/type), so they must not share a key.
        suffix = attrs.get('hreflang') or attrs.get('type') or ''
        entry_key = key or f'link:{rel}' + (f':{suffix}' if suffix else '')
        if not (href or '').strip():
            self._entries.pop(entry_key, None)
            return
        merged = {'rel': rel, 'href': href.strip()}
        merged.update({k: v for k, v in attrs.items() if v})
        self._put(
            HeadEntry(
                section='link',
                key=entry_key,
                attrs=merged,
                source=source or self._default_source,
                order=order,
            )
        )

    def jsonld(
        self, data, *, key: str = 'jsonld:graph', source: str = '', order: int = 100
    ) -> None:
        """Add/replace a JSON-LD block. Empty data removes it.

        One block per key; the SEO app emits a single `@graph` under the default
        key, so page templates that used to add their own node now enrich the
        graph through `SEO_JSONLD_GRAPH` instead of stacking scripts.
        """
        if not data:
            self._entries.pop(key, None)
            return
        self._put(
            HeadEntry(
                section='jsonld',
                key=key,
                content=_dump_jsonld(data),
                source=source or self._default_source,
                order=order,
            )
        )

    def raw(self, html: str, *, key: str, source: str = '', order: int = 200) -> None:
        """Escape hatch for markup with no first-class representation.

        Trusted, internally-generated HTML only — it is emitted verbatim.
        """
        if not (html or '').strip():
            self._entries.pop(key, None)
            return
        self._put(
            HeadEntry(
                section='raw',
                key=key,
                content=html,
                source=source or self._default_source,
                order=order,
            )
        )

    def remove(self, key: str) -> None:
        self._entries.pop(key, None)

    def note(self, message: str) -> None:
        """Record why a decision was made (e.g. 'noindex: facet param `sort`')."""
        if message:
            self.notes.append(message)

    def _put(self, entry: HeadEntry) -> None:
        self._entries[entry.key] = entry

    # -- reading ---------------------------------------------------------
    def get(self, key: str) -> HeadEntry | None:
        return self._entries.get(key)

    @property
    def title(self) -> str:
        entry = self._entries.get('title')
        return entry.content if entry else ''

    def meta_content(self, name: str) -> str:
        entry = self._entries.get(f'meta:{name}')
        return entry.attrs.get('content', '') if entry else ''

    def link_href(self, rel: str) -> str:
        entry = self._entries.get(f'link:{rel}')
        return entry.attrs.get('href', '') if entry else ''

    def entries(self) -> list[HeadEntry]:
        return sorted(
            self._entries.values(),
            key=lambda e: (_SECTION_ORDER.index(e.section), e.order, e.key),
        )

    def as_dict(self) -> dict:
        """JSON-serialisable form — the headless/GraphQL representation."""
        out: dict = {
            'path': self.path,
            'language': self.language,
            'title': self.title,
            'meta': [],
            'links': [],
            'jsonld': [],
            'raw': [],
            'notes': list(self.notes),
        }
        for entry in self.entries():
            if entry.section == 'title':
                continue
            if entry.section == 'meta':
                out['meta'].append(dict(entry.attrs))
            elif entry.section == 'link':
                out['links'].append(dict(entry.attrs))
            elif entry.section == 'jsonld':
                with suppress(ValueError):  # content is our own dump
                    out['jsonld'].append(json.loads(entry.content))
            else:
                out['raw'].append(entry.content)
        return out

    def render(self) -> str:
        parts: list[str] = []
        for entry in self.entries():
            if entry.section == 'title':
                parts.append(f'<title>{escape(entry.content)}</title>')
            elif entry.section in ('meta', 'link'):
                attrs = ' '.join(
                    f'{k}="{escape(str(v), quote=True)}"' for k, v in entry.attrs.items()
                )
                parts.append(f'<{entry.section} {attrs}>')
            elif entry.section == 'jsonld':
                parts.append(f'<script type="application/ld+json">{entry.content}</script>')
            else:
                parts.append(entry.content)
        return '\n'.join(parts)


def _dump_jsonld(data) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=str)
    for needle, replacement in _JSONLD_ESCAPES:
        payload = payload.replace(needle, replacement)
    return payload


def build_head(
    *,
    path: str = '',
    language: str = '',
    request=None,
    context=None,
    title: str = '',
    description: str = '',
) -> HeadDocument:
    """Seed a document with the shell's fallbacks and let subscribers finish it.

    The seed is what a storefront guarantees on its own: a title and (when the
    view supplied one) a description. Everything else — canonical, robots, Open
    Graph, hreflang, JSON-LD — arrives from `STOREFRONT_HEAD` subscribers, so a
    store with the SEO app disabled degrades to a plain but valid head instead
    of a broken one.
    """
    from core.hooks import MorpheusEvents, hook_registry

    doc = HeadDocument(path=path, language=language)
    if title:
        doc.set_title(title, source='shell')
    if description:
        doc.meta(description, name='description', source='shell')
    return hook_registry.filter(
        MorpheusEvents.STOREFRONT_HEAD, doc, request=request, context=context
    )
