---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/digital_products/management/commands/convert_gutenberg_to_dotbooks.py

Symbols in `plugins/installed/digital_products/management/commands/convert_gutenberg_to_dotbooks.py`.

- L50 `_strip_gutenberg(raw: str)` (function)
- L62 `_gutenberg_id_for(product)` (function) — Resolve a Gutenberg ID either from an image filename or a metafield.
- L88 `_build_epub(*, title: str, author: str, body_text: str)` (function) — Generate a minimal valid EPUB 3 file from cleaned plain text.
- L161 `_build_pdf(*, title: str, author: str, body_text: str)` (function) — Generate a PDF rendering of the book via reportlab.
- L228 `_book_meta(product)` (function) — Return (title, author) for a product from its book.* metafields.
- L251 `_set_metafield(product, *, namespace: str, key: str, value: str)` (function)
- L266 `Command` (class)
- L269 `add_arguments(self, parser)` (method)
- L285 `handle(self, *args, **opts)` (method)
