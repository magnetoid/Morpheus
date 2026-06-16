---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/i18n/services.py

Symbols in `core/i18n/services.py`.

- L10 `_ct(obj)` (function)
- L16 `set_translation(obj, field: str, language_code: str, value: str, *, machine_translated: bool=False)` (function)
- L32 `get_translation(obj, field: str, language_code: str)` (function)
- L47 `translated(obj, field: str, language_code: str='')` (function) — Return translation if present, else fall back to the model value.
- L56 `translations_for(obj, *, language_code: str='')` (function) — All translations for `obj` (optionally filtered by language).
- L67 `bulk_set_translations(obj, language_code: str, mapping: dict)` (function) — Set multiple field translations at once: `mapping = {field: value}`.
- L86 `list_enabled_languages()` (function) — Return the list of ISO codes the store is configured to ship to.
- L102 `set_enabled_languages(codes: list[str])` (function) — Persist the list of enabled language ISO codes; returns the saved list.
