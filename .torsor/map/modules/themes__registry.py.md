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

# themes/registry.py

Symbols in `themes/registry.py`.

- L22 `ThemeRegistry` (class)
- L23 `__init__(self)` (method)
- L29 `discover(self, themes_dir: Path)` (method)
- L65 `_find_theme_class(module, base)` (method)
- L79 `set_active(self, name: str)` (method) — Activate a theme by name. Logs a warning if not discovered.
- L92 `set_active_from_db(self)` (method) — Read active theme from DB (ThemeConfig) or fall back to settings.
- L111 `validate_active_theme(self)` (method) — Return a list of error strings if the active theme is misconfigured.
- L118 `validate_active_theme_for(self, name: str)` (method) — Validate a theme by name — whether it may be activated on this store.
- L147 `active(self)` (method)
- L151 `active_templates_dir(self)` (method)
- L155 `all_themes(self)` (method)
- L158 `get(self, name: str)` (method)
- L161 `__repr__(self)` (method)
