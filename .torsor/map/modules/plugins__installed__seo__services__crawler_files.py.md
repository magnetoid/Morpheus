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

# plugins/installed/seo/services/crawler_files.py

Symbols in `plugins/installed/seo/services/crawler_files.py`.

- L56 `get_ai_crawler_policy()` (function) — Read per-bot allow/disallow policy from seo plugin config.
- L74 `render_robots_txt()` (function) — robots.txt with explicit AI-crawler blocks.
- L144 `_robots_document()` (function) — Seed the document with what seo owns, then let the owners answer.
- L191 `render_llms_txt(*, full: bool=False)` (function) — Generate /llms.txt (compact) or /llms-full.txt (with product summaries).
- L316 `_contributed_llms_sections(*, base: str, full: bool)` (function) — `SEO_LLMS_SECTIONS` subscribers append their own catalogue sections.
- L338 `render_agents_md()` (function) — Generate /agents.md — the agent-onboarding manifest.
