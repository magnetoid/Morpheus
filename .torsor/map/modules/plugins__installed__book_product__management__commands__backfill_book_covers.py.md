---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/book_product/management/commands/backfill_book_covers.py

Symbols in `plugins/installed/book_product/management/commands/backfill_book_covers.py`.

- L66 `_font(path: str, size: int)` (function)
- L75 `_wrap(draw, text: str, font, max_w: int)` (function) — Greedy word-wrap to a pixel width.
- L92 `render_cover_bytes(*, title: str, author: str='', genre: str='', slug: str='')` (function) — Render an 800×1200 styled classic-cover JPEG. Pure function — unit-tested.
- L153 `_gutenberg_cover_bytes(gid: str)` (function) — Fetch the real Gutenberg cover for `gid`; None if unavailable/bad.
- L174 `Command` (class)
- L177 `add_arguments(self, parser)` (method)
- L182 `handle(self, *args, **opts)` (method)
- L221 `_book_meta(self, p)` (method) — (author, genre_name, gutenberg_id) for a product, best-effort.
- L242 `_save(self, p, data: bytes, ProductImage, *, alt: str)` (method)
