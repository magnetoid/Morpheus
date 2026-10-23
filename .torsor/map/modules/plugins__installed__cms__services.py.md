---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/cms/services.py

Symbols in `plugins/installed/cms/services.py`.

- L16 `get_live_page(slug: str)` (function) — Resolve a slug to a published Page (respects publish_at).
- L28 `_str_list(value)` (function) — Coerce a free-form ``page.metadata`` value into a clean ``list[str]``.
- L58 `strip_duplicate_heading(body: str)` (function) — Drop a leading <h1> (and the byline right under it) from a journal body.
- L87 `_plain(fragment: str)` (function)
- L91 `_pair(question: str, section: str)` (function) — One Q&A, or None when the heading is not a question or the answer is thin.
- L106 `journal_faq_pairs(body: str)` (function) — Q&A pairs for `FAQPage`, taken only from Q&A the article really shows.
- L137 `_default_author()` (function) — Fallback byline for a journal entry with no explicit author — the
- L145 `journal_dict(page)` (function) — The render/SEO dict for a journal ``Page``. Public — the storefront
- L197 `journal_pages()` (function) — Live journal posts, newest first — a queryset, so a listing can paginate it.
- L208 `list_journal_entries(*, limit: int=50)` (function) — Published CMS pages tagged with metadata.category == 'journal'.
- L213 `get_journal_page(slug: str)` (function) — The underlying published journal ``Page`` instance (not the dict).
- L232 `get_journal_entry(slug: str)` (function) — Single published journal entry by slug, or None.
- L238 `render_block(key: str)` (function)
- L256 `get_menu(key: str)` (function)
- L286 `submit_form(*, form, payload: dict, request=None)` (function) — Persist a FormSubmission, fire `cms.form_submitted` hook.
