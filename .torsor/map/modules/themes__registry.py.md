---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# themes/registry.py

Symbols in `themes/registry.py`.

- L21 `ThemeRegistry` (class)
- L22 `__init__(self)` (method)
- L28 `discover(self, themes_dir: Path)` (method)
- L56 `_find_theme_class(module, base)` (method)
- L70 `set_active(self, name: str)` (method) — Activate a theme by name. Logs a warning if not discovered.
- L81 `set_active_from_db(self)` (method) — Read active theme from DB (ThemeConfig) or fall back to settings.
- L99 `validate_active_theme(self)` (method) — Return a list of error strings if the active theme is misconfigured.
- L120 `active(self)` (method)
- L124 `active_templates_dir(self)` (method)
- L128 `all_themes(self)` (method)
- L131 `get(self, name: str)` (method)
- L134 `__repr__(self)` (method)
