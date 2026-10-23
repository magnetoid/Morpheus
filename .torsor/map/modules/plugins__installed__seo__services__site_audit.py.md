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

# plugins/installed/seo/services/site_audit.py

Symbols in `plugins/installed/seo/services/site_audit.py`.

- L68 `Finding` (class)
- L78 `as_dict(self)` (method)
- L83 `PageFacts` (class) — What one URL actually returned. Everything else is derived from these.
- L101 `NotFoundFacts` (class) — How the store answers a URL that cannot exist.
- L111 `_facts(client, path: str, host: str)` (function) — Fetch one URL through the real stack and read its head.
- L168 `_probe_missing(client, host: str)` (function) — Ask for a URL that cannot exist and read what comes back.
- L204 `_not_found_findings(probe: NotFoundFacts)` (function) — Findings about how the store answers a missing page.
- L240 `_first(pattern, html: str)` (function)
- L245 `_paths(limit: int | None)` (function) — Every URL the store publishes, as site-relative paths.
- L268 `collect(*, limit: int | None=None)` (function) — Crawl the sitemap in-process and return findings + a score.
- L316 `_analyse(pages: list[PageFacts])` (function) — Turn page facts into findings, most severe first.
- L534 `_coverage(pages: list[PageFacts])` (function) — What share of live pages carries each head element.
- L557 `cached()` (function) — The last stored report, or None when nothing has run yet.
- L565 `run_and_store(*, limit: int | None=None)` (function)
