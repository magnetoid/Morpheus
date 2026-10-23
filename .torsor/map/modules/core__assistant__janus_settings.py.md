---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/assistant/janus_settings.py

Symbols in `core/assistant/janus_settings.py`.

- L30 `_read(key: str, default: Any)` (function)
- L44 `_int(key: str, default: int, low: int, high: int)` (function)
- L51 `engine_enabled()` (function)
- L55 `max_tool_turns(default: int)` (function)
- L59 `turn_timeout_s(default: int)` (function)
- L63 `extra_instructions()` (function)
- L67 `bundled_skills_enabled()` (function)
- L77 `reasoning_effort()` (function)
- L82 `learning_enabled()` (function) — Whether Janus keeps what it learns (core/assistant/janus_learning.py).
- L87 `web_search_enabled()` (function) — Whether Linda may search the web. Her queries go to a public search engine.
- L92 `auto_update_enabled()` (function) — Whether Janus installs newer commits from its GitHub branch by itself
- L99 `fallback_providers()` (function) — Backup providers, in order, for when the main one fails (provider names).
- L111 `custom_provider()` (function) — The merchant's pinned provider for Janus, or None to use the store's AI provider.
