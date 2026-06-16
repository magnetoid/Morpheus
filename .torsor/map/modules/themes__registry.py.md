---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# themes/registry.py

Symbols in `themes/registry.py`.

- L22 `ThemeRegistry` (class)
- L23 `__init__(self)` (method)
- L29 `discover(self, themes_dir: Path)` (method)
- L59 `_find_theme_class(module, base)` (method)
- L73 `set_active(self, name: str)` (method) — Activate a theme by name. Logs a warning if not discovered.
- L86 `set_active_from_db(self)` (method) — Read active theme from DB (ThemeConfig) or fall back to settings.
- L105 `validate_active_theme(self)` (method) — Return a list of error strings if the active theme is misconfigured.
- L127 `active(self)` (method)
- L131 `active_templates_dir(self)` (method)
- L135 `all_themes(self)` (method)
- L138 `get(self, name: str)` (method)
- L141 `__repr__(self)` (method)
