---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# themes/base.py

Symbols in `themes/base.py`.

- L29 `ThemeConfigurationError` (class) — Raised when a theme's metadata is invalid at class-definition time.
- L33 `MorpheusTheme` (class) — Base class for all Morph themes.
- L95 `__init_subclass__(cls, **kwargs: Any)` (method)
- L102 `_validate_metadata(cls)` (method)
- L125 `get_config_schema(self)` (method) — JSON Schema for *behavioral* settings (e.g. show/hide a section).
- L129 `get_design_tokens(self)` (method) — Design-token surface. Returned dict is a flat tree of token
- L140 `get_config(self)` (method)
- L155 `get_config_value(self, key: str, default: Any=None)` (method)
- L162 `invalidate_config_cache(self)` (method)
- L168 `templates_dir(self)` (method)
- L174 `static_dir(self)` (method)
- L180 `preview_url(self)` (method) — Static URL of this theme's preview image, or '' if unset.
- L190 `__repr__(self)` (method)
