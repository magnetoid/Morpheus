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

# themes/base.py

Symbols in `themes/base.py`.

- L29 `ThemeConfigurationError` (class) — Raised when a theme's metadata is invalid at class-definition time.
- L33 `MorpheusTheme` (class) — Base class for all Morph themes.
- L112 `__init_subclass__(cls, **kwargs: Any)` (method)
- L119 `_validate_metadata(cls)` (method)
- L142 `get_config_schema(self)` (method) — JSON Schema for *behavioral* settings (e.g. show/hide a section).
- L146 `get_design_tokens(self)` (method) — Design-token surface. Returned dict is a flat tree of token
- L157 `get_config(self)` (method)
- L172 `get_config_value(self, key: str, default: Any=None)` (method)
- L179 `invalidate_config_cache(self)` (method)
- L185 `templates_dir(self)` (method)
- L191 `static_dir(self)` (method)
- L197 `preview_url(self)` (method) — Static URL of this theme's preview image, or '' if unset.
- L207 `__repr__(self)` (method)
