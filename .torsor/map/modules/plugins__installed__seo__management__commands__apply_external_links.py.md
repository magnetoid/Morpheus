---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/seo/management/commands/apply_external_links.py

Symbols in `plugins/installed/seo/management/commands/apply_external_links.py`.

- L54 `_read_identifiers(product)` (function) — ISBN-13 / OCLC / Open Library work id from the shared metafield store.
- L75 `_read_author(product)` (function) — Author name — prefer the BookProduct model column, fall back to the
- L93 `_verify_wikipedia(author: str)` (function) — Return the canonical Wikipedia URL for ``author`` iff a real article
- L122 `_ext(href: str, label: str)` (function)
- L129 `_build_links(product, *, verify_web: bool)` (function) — Ordered list of verified external <a> links for this book.
- L153 `_block(links: list[str])` (function)
- L158 `_strip_previous(body: str)` (function)
- L165 `Command` (class)
- L168 `add_arguments(self, parser)` (method)
- L181 `handle(self, *args, **opts)` (method)
