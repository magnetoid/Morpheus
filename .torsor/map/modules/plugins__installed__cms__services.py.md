---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/cms/services.py

Symbols in `plugins/installed/cms/services.py`.

- L15 `get_live_page(slug: str)` (function) — Resolve a slug to a published Page (respects publish_at).
- L27 `_journal_dict(page)` (function)
- L55 `list_journal_entries(*, limit: int=50)` (function) — Published CMS pages tagged with metadata.category == 'journal'.
- L67 `get_journal_entry(slug: str)` (function) — Single published journal entry by slug, or None.
- L79 `render_block(key: str)` (function)
- L97 `get_menu(key: str)` (function)
- L127 `submit_form(*, form, payload: dict, request=None)` (function) — Persist a FormSubmission, fire `cms.form_submitted` hook.
