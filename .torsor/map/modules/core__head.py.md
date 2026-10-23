---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/head.py

Symbols in `core/head.py`.

- L45 `HeadEntry` (class) — One renderable thing in the head.
- L56 `HeadDocument` (class) — A mutable, keyed description of a page's `<head>`.
- L64 `__init__(self, *, path: str='', language: str='', source: str='core')` (method)
- L72 `set_title(self, title: str, *, source: str='', order: int=0)` (method)
- L83 `meta(self, content: str, *, name: str='', property: str='', key: str='', source: str='', order: int=100)` (method) — Add/replace a `<meta>`. Empty content removes the entry.
- L117 `link(self, rel: str, href: str, *, key: str='', source: str='', order: int=100, **attrs: str)` (method) — Add/replace a `<link>`. Empty href removes the entry.
- L148 `jsonld(self, data, *, key: str='jsonld:graph', source: str='', order: int=100)` (method) — Add/replace a JSON-LD block. Empty data removes it.
- L170 `raw(self, html: str, *, key: str, source: str='', order: int=200)` (method) — Escape hatch for markup with no first-class representation.
- L188 `remove(self, key: str)` (method)
- L191 `note(self, message: str)` (method) — Record why a decision was made (e.g. 'noindex: facet param `sort`').
- L196 `_put(self, entry: HeadEntry)` (method)
- L200 `get(self, key: str)` (method)
- L204 `title(self)` (method)
- L208 `meta_content(self, name: str)` (method)
- L212 `link_href(self, rel: str)` (method)
- L216 `entries(self)` (method)
- L222 `as_dict(self)` (method) — JSON-serialisable form — the headless/GraphQL representation.
- L248 `render(self)` (method)
- L265 `_dump_jsonld(data)` (function)
- L272 `build_head(*, path: str='', language: str='', request=None, context=None, title: str='', description: str='')` (function) — Seed a document with the shell's fallbacks and let subscribers finish it.
