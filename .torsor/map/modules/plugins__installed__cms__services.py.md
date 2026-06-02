---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/cms/services.py

Symbols in `plugins/installed/cms/services.py`.

- L12 `get_live_page(slug: str)` (function) — Resolve a slug to a published Page (respects publish_at).
- L24 `_journal_dict(page)` (function)
- L36 `list_journal_entries(*, limit: int=50)` (function) — Published CMS pages tagged with metadata.category == 'journal'.
- L47 `get_journal_entry(slug: str)` (function) — Single published journal entry by slug, or None.
- L58 `render_block(key: str)` (function)
- L71 `get_menu(key: str)` (function)
- L89 `submit_form(*, form, payload: dict, request=None)` (function) — Persist a FormSubmission, fire `cms.form_submitted` hook.
