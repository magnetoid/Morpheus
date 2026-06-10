---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# themes/sections.py

Symbols in `themes/sections.py`.

- L45 `Section` (class) — Subclass and override class attributes (or use as-is).
- L55 `render_context(self, *, page, settings: dict)` (method) — Build the template context for a single render.
- L72 `SectionRegistry` (class)
- L73 `__init__(self)` (method)
- L76 `register(self, section_cls: type[Section] | Section)` (method) — Decorator-friendly registration. Accepts a class or an instance.
- L84 `get(self, section_id: str)` (method)
- L87 `all(self)` (method)
- L90 `__contains__(self, section_id: str)` (method)
- L97 `render_section(*, page, section_id: str, settings: dict)` (function) — Resolve a section by id and return ``(template, context)`` ready
