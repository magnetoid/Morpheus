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

# core/assistant/modes.py

Symbols in `core/assistant/modes.py`.

- L29 `AssistantMode` (class) — One row in the mode catalogue.
- L115 `get_mode(slug: str | None)` (function) — Resolve a mode by slug. Falls back to ``general`` for unknown /
- L126 `allowed_modes_for(user)` (function) — Modes the acting user may use. ``dev`` exposes diagnostics (filesystem,
- L140 `resolve_mode(slug: str | None, user)` (function) — Server-side mode resolution: honour the client's requested mode only when
- L157 `filter_tools_by_mode(tools: list, mode_slug: str | None)` (function) — Return the subset of ``tools`` allowed by the named mode.
