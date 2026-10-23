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

# plugins/installed/seo/services/templating.py

Symbols in `plugins/installed/seo/services/templating.py`.

- L49 `_compile()` (function) — {(kind, field): [row dicts, most-specific first]} from active rows.
- L69 `_rules()` (function)
- L77 `invalidate_templates()` (function)
- L84 `_category_slug(obj)` (function)
- L94 `_dict_field(obj: dict, key: str)` (function) — The PDP renders a GraphQL dict (camelCase); map the token vocabulary
- L112 `_token_values(obj, kind: str)` (function) — The full vocabulary for one render: site tokens + object fields +
- L168 `_apply_filter(value: str, spec: str)` (function)
- L181 `_eval_token(body: str, values: dict)` (function) — One `{…}` expression → (text, any_token_resolved).
- L211 `render_template(text: str, obj, kind: str='')` (function) — Render one pattern against one object. Empty result = template declined
- L250 `apply_templates(kind: str, obj, title: str, description: str)` (function) — Apply the matching template per field. `title`/`description` arrive as
