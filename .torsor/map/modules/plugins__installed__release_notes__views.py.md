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

# plugins/installed/release_notes/views.py

Symbols in `plugins/installed/release_notes/views.py`.

- L31 `_release_notes_path()` (function)
- L35 `_inline(text: str)` (function) — Escape, then apply safe inline formatting (links / bold / code).
- L44 `_md_to_html(body: str)` (function) — Minimal markdown → HTML for the release-notes subset. Input is escaped.
- L89 `parse_releases(raw: str)` (function) — Split RELEASE_NOTES.md on `## ` headings into release cards.
- L116 `_with_times(record: dict | None)` (function) — A restore record with its ISO times as datetimes, for the |date filter.
- L131 `version_updates(request)` (function) — The one "Version & updates" page: the running version, the updater
- L182 `_site_page(request, page: str, title: str)` (function) — A page of the project website, shown inside the dashboard.
- L210 `about(request)` (function) — About Morpheus OS — the website's About page.
