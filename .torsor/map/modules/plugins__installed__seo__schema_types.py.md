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

# plugins/installed/seo/schema_types.py

Symbols in `plugins/installed/seo/schema_types.py`.

- L215 `registry_json()` (function) — The type spec the editor JS renders forms from (safe to JSON-encode).
- L223 `_s(data: dict, key: str)` (function)
- L227 `_rows(data: dict, key: str)` (function)
- L232 `_iso_duration(minutes: Any)` (function) — Whole minutes → ISO-8601 duration (PT1H30M). Empty/invalid → ''.
- L244 `_clean(value: Any)` (function) — Drop empty strings / empty lists / empty dicts recursively.
- L258 `_build_faq(d: dict)` (function)
- L271 `_build_howto(d: dict)` (function)
- L294 `_build_event(d: dict)` (function)
- L315 `_build_recipe(d: dict)` (function)
- L332 `_build_article(d: dict)` (function)
- L348 `_build_book(d: dict)` (function)
- L372 `_build_video(d: dict)` (function)
- L384 `_build_course(d: dict)` (function)
- L394 `_build_custom(d: dict)` (function)
- L416 `build_block(type_key: str, data: dict)` (function) — Turn one editor entry into a JSON-LD block (with @context), or None if the
- L429 `build_blocks(entries: list[dict])` (function) — Map a posted ``[{type, data}, …]`` list to clean JSON-LD blocks.
