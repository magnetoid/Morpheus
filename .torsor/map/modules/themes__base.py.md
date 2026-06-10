---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:51'
updated: '2026-06-10T20:08:51'
---

# themes/base.py

Symbols in `themes/base.py`.

- L28 `ThemeConfigurationError` (class) — Raised when a theme's metadata is invalid at class-definition time.
- L32 `MorpheusTheme` (class) — Base class for all Morph themes.
- L94 `__init_subclass__(cls, **kwargs: Any)` (method)
- L101 `_validate_metadata(cls)` (method)
- L124 `get_config_schema(self)` (method) — JSON Schema for *behavioral* settings (e.g. show/hide a section).
- L128 `get_design_tokens(self)` (method) — Design-token surface. Returned dict is a flat tree of token
- L139 `get_config(self)` (method)
- L152 `get_config_value(self, key: str, default: Any=None)` (method)
- L159 `invalidate_config_cache(self)` (method)
- L165 `templates_dir(self)` (method)
- L170 `static_dir(self)` (method)
- L175 `preview_url(self)` (method) — Static URL of this theme's preview image, or '' if unset.
- L184 `__repr__(self)` (method)
