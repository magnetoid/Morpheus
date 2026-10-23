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

# scripts/check_plugin_boundary.py

Symbols in `scripts/check_plugin_boundary.py`.

- L50 `_is_test_path(p: Path)` (function)
- L55 `_plugin_names()` (function)
- L59 `_requires_of(name: str)` (function) — Parse the `requires = [...]` class attribute from a plugin's app.py.
- L88 `_target_plugin(module: str, plugins: set[str])` (function) — `plugins.installed.orders.models` -> `orders` (if it's a real plugin).
- L97 `_scan()` (function) — Return {(importer_plugin, target_plugin)} for every UNDECLARED cross-plugin import.
- L125 `_load_baseline()` (function)
- L132 `_save_baseline(found: set[tuple[str, str]])` (function)
- L148 `main(argv: list[str])` (function)
