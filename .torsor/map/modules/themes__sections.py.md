---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# themes/sections.py

Symbols in `themes/sections.py`.

- L46 `Section` (class) — Subclass and override class attributes (or use as-is).
- L57 `render_context(self, *, page, settings: dict)` (method) — Build the template context for a single render.
- L74 `SectionRegistry` (class)
- L75 `__init__(self)` (method)
- L78 `register(self, section_cls: type[Section] | Section)` (method) — Decorator-friendly registration. Accepts a class or an instance.
- L86 `get(self, section_id: str)` (method)
- L89 `all(self)` (method)
- L92 `__contains__(self, section_id: str)` (method)
- L99 `render_section(*, page, section_id: str, settings: dict)` (function) — Resolve a section by id and return ``(template, context)`` ready
