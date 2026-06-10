---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/admin_dashboard/forms/_helpers.py

Symbols in `plugins/installed/admin_dashboard/forms/_helpers.py`.

- L15 `_money(amount: str | Decimal | None, currency: str='USD')` (function) — Return a djmoney `Money` from a raw string, or None if blank.
- L29 `_md_to_html(value: str)` (function) — Minimal Markdown → HTML for the subset our LLM produces.
- L75 `_ensure_html(value: str | None)` (function) — Return HTML, converting legacy Markdown when needed.
- L90 `DashboardFormMixin` (class) — Auto-attach the dashboard's semantic ``.input`` CSS class to every
- L102 `__init__(self, *args, **kwargs)` (method)
