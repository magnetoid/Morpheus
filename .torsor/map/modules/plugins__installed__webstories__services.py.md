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

# plugins/installed/webstories/services.py

Symbols in `plugins/installed/webstories/services.py`.

- L78 `Text` (class) — Rich text as blocks: paragraphs and list items, each plain.
- L86 `_Extractor` (class)
- L87 `__init__(self)` (method)
- L94 `_flush(self)` (method)
- L102 `handle_starttag(self, tag, attrs)` (method)
- L113 `handle_endtag(self, tag)` (method)
- L122 `handle_data(self, data)` (method)
- L126 `close(self)` (method)
- L131 `_extract_plain(raw: str)` (function) — Text with no markup: blank lines part paragraphs, ``- `` lines are items.
- L158 `extract(value)` (function) — Paragraphs and list items of a product's rich (or plain) text.
- L172 `plain_text(value)` (function) — One line of plain text; blocks end with a full stop when they have none.
- L180 `clip(text: str, limit: int)` (function) — ``text`` cut to ``limit`` characters at a sentence end, else a word (…).
- L200 `sentences(text: str)` (function)
- L204 `_lead(parts: list[str], limit: int)` (function) — As many opening sentences as fit in ``limit``, and how many were used.
- L217 `_same(a: str, b: str)` (function) — Do two texts say the same thing (one opens with the other)?
- L226 `_image_url_for(image_row)` (function) — Prefer the WebP variant (smaller, AMP-friendly) when present.
- L235 `_local_name(image_row)` (function) — The media-relative file name when the file is on local storage — what
- L251 `_open_rgb(name: str)` (function) — The stored photo as an RGB Pillow image; transparency becomes white.
- L268 `_border(img)` (function) — The median colour of the photo's outer edge, and how much it varies.
- L290 `_look(name: str)` (function) — How a photo sits on a page: shown whole on its own background colour
- L317 `_render_poster(data_name: str)` (function) — The 3:4 poster JPEG for a stored photo.
- L334 `_media_name(url: str)` (function)
- L341 `_poster_for(product, image_row)` (function) — URL of the product's 3:4 poster, made once per photo; '' on failure.
- L366 `_drop_old_poster(old_url: str, new_url: str)` (function)
- L383 `_book_metafields(product)` (function) — Book attributes (synopsis / author / …) for the story panels.
- L405 `_Images` (class) — Hands out the product's photos in order, then the main one again.
- L408 `__init__(self, rows: list)` (method)
- L412 `take(self)` (method)
- L421 `rest(self)` (method)
- L427 `_page(kind: str, image_row, *, alt_fallback: str, **fields)` (function)
- L439 `build_panels_for(product)` (function) — Pages for ``product``, each saying one thing. Side-effect-free.
- L522 `ensure_story(product)` (function) — Get-or-create the WebStory for ``product``, rebuild its pages and poster.
- L555 `is_current(story)` (function) — Was ``story`` built by this builder?
- L564 `render_pages(panels: list, *, base: str, image_proxy: bool, fallback_alt: str)` (function) — The pages as the template draws them, whatever builder made them.
- L606 `story_path(product_slug: str)` (function)
