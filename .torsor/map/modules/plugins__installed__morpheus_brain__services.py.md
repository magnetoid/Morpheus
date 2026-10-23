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

# plugins/installed/morpheus_brain/services.py

Symbols in `plugins/installed/morpheus_brain/services.py`.

- L37 `_derive_title(text: str)` (function) — First heading line → title; else a dated default.
- L48 `_derive_summary(text: str)` (function) — First non-heading, non-empty paragraph → short scannable lead.
- L57 `generate_briefing()` (function) — Generate + persist a long-form AI advisory briefing. Returns a small
