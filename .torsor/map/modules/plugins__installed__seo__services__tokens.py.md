---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/seo/services/tokens.py

Symbols in `plugins/installed/seo/services/tokens.py`.

- L30 `_field_value(obj, key: str)` (function)
- L42 `_metafields(obj)` (function) — ``{"namespace.key": value}`` for obj, or {} (fail-soft).
- L52 `expand_tokens(text: str, obj)` (function) — Replace ``{token}`` in ``text`` with product field / metafield values.
- L78 `available_tokens(obj)` (function) — ``[{token, label}]`` for the editor's "Insert field" dropdown.
