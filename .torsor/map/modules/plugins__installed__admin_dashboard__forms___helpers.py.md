---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/admin_dashboard/forms/_helpers.py

Symbols in `plugins/installed/admin_dashboard/forms/_helpers.py`.

- L16 `_money(amount: str | Decimal | None, currency: str='USD')` (function) — Return a djmoney `Money` from a raw string, or None if blank.
- L31 `_md_to_html(value: str)` (function) — Minimal Markdown → HTML for the subset our LLM produces.
- L77 `_ensure_html(value: str | None)` (function) — Return HTML, converting legacy Markdown when needed.
- L92 `DashboardFormMixin` (class) — Auto-attach the dashboard's semantic ``.input`` CSS class to every
- L104 `__init__(self, *args, **kwargs)` (method)
