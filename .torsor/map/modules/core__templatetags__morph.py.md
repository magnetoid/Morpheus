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

# core/templatetags/morph.py

Symbols in `core/templatetags/morph.py`.

- L44 `first_sentence(text)` (function) — First sentence of `text` — up to the first . ! or ?, trimmed, capped at
- L71 `plugin_enabled(slug: str)` (function) — True when the plugin `slug` is currently active.
- L93 `storefront_blocks(context, slot: str)` (function) — Render every storefront block contributed for `slot`.
- L128 `page_href(context, number)` (function) — `{% page_href page_obj.previous_page_number %}` — the link to a page of this listing.
- L144 `storefront_head(context, title: str='', description: str='')` (function) — Render the whole SEO head: title, metas, canonical, robots, OG, JSON-LD.
- L223 `money_filter(value, _arg=None)` (function) — Render a Money instance OR a GraphQL `{amount, currency}` dict.
- L265 `convert_money(value, target_currency: str)` (function) — Convert a Money value to the target currency using the latest ExchangeRate.
- L298 `markdown_to_html(value: str)` (function) — Minimal Markdown → HTML for the subset our LLM produces.
- L352 `markdown_safe(value)` (function) — Template-filter wrapper around ``markdown_to_html``.
- L368 `ai_disclosure(surface: str='')` (function) — Render the Art. 50 AI-disclosure label for a conversational AI surface.
- L401 `image_frame_style()` (function) — CSS custom properties for the store's image frame, for either shell.
- L437 `error_capture_attrs()` (function) — Attributes for the error-capture.js <script> tag.
- L453 `product_card_meta(product)` (function) — Extra lines for a storefront product card, from the apps that own them
