---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/i18n/services.py

Symbols in `core/i18n/services.py`.

- L10 `_ct(obj)` (function)
- L15 `set_translation(obj, field: str, language_code: str, value: str, *, machine_translated: bool=False)` (function)
- L27 `get_translation(obj, field: str, language_code: str)` (function)
- L39 `translated(obj, field: str, language_code: str='')` (function) — Return translation if present, else fall back to the model value.
- L48 `translations_for(obj, *, language_code: str='')` (function) — All translations for `obj` (optionally filtered by language).
- L58 `bulk_set_translations(obj, language_code: str, mapping: dict)` (function) — Set multiple field translations at once: `mapping = {field: value}`.
- L77 `list_enabled_languages()` (function) — Return the list of ISO codes the store is configured to ship to.
- L92 `set_enabled_languages(codes: list[str])` (function) — Persist the list of enabled language ISO codes; returns the saved list.
