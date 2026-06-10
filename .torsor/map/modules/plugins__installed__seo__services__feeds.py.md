---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/seo/services/feeds.py

Symbols in `plugins/installed/seo/services/feeds.py`.

- L33 `_summary(body: str, max_chars: int=280)` (function) — First ``max_chars`` of the body, HTML/Markdown stripped to plain text.
- L45 `_journal_posts(limit: int=50)` (function) — Yield journal Page rows. Empty list when cms is uninstalled.
- L60 `_author_of(post)` (function)
- L68 `render_journal_rss()` (function) — RSS 2.0 feed for the journal — top 50 published posts.
- L114 `render_journal_atom()` (function) — Atom 1.0 feed for the journal — top 50 published posts.
