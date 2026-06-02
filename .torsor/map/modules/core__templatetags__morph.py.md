---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/templatetags/morph.py

Symbols in `core/templatetags/morph.py`.

- L39 `plugin_enabled(slug: str)` (function) — True when the plugin `slug` is currently active.
- L61 `storefront_blocks(context, slot: str)` (function) — Render every storefront block contributed for `slot`.
- L120 `money_filter(value, _arg=None)` (function) — Render a Money instance OR a GraphQL `{amount, currency}` dict.
- L162 `convert_money(value, target_currency: str)` (function) — Convert a Money value to the target currency using the latest ExchangeRate.
- L195 `markdown_to_html(value: str)` (function) — Minimal Markdown → HTML for the subset our LLM produces.
- L244 `markdown_safe(value)` (function) — Template-filter wrapper around ``markdown_to_html``.
