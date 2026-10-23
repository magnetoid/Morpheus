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

# scripts/check_plugin_standard.py

Symbols in `scripts/check_plugin_standard.py`.

- L84 `_manifest_bases(node: ast.ClassDef)` (function)
- L94 `_literal(node: ast.ClassDef, field: str)` (function) — The literal value assigned to `field` in a class body, or None.
- L113 `_parse(path: Path)` (function)
- L120 `_classes(path: Path, base_suffixes: tuple[str, ...])` (function)
- L132 `registered_apps()` (function) — The app names listed in MORPHEUS_DEFAULT_APPS, read without importing.
- L149 `defines_models(plugin: Path)` (function) — True when models.py declares something that looks like a concrete model.
- L163 `_check_structure(plugin: Path)` (function)
- L178 `_check_manifest(plugin: Path, manifest: ast.ClassDef | None, *, known: set[str])` (function)
- L209 `_check_models(plugin: Path, manifest: ast.ClassDef | None)` (function)
- L228 `audit_plugin(plugin: Path, *, known: set[str], registered: set[str])` (function) — Return [(rule_id, detail)] for one app directory.
- L251 `audit_all()` (function)
- L264 `_flatten(found: dict[str, list[tuple[str, str]]])` (function) — One comparable key per violation: `<app>:<rule>` (the detail is advisory).
- L269 `load_baseline()` (function)
- L276 `save_baseline(found: dict[str, list[tuple[str, str]]])` (function)
- L296 `report(found: dict[str, list[tuple[str, str]]])` (function)
- L313 `main()` (function)
