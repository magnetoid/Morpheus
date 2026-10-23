---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# plugins/app_help.py

Symbols in `plugins/app_help.py`.

- L58 `Guide` (class)
- L66 `parse(app: str, text: str)` (function) — A guide from its file's text. Front matter is ``key: value`` lines between ``---``.
- L85 `markers(body: str)` (function) — ``(text, kind, target)`` for every marker in a guide's body.
- L90 `tree_apps()` (function) — Every app folder in the repository (``plugins/installed/*/app.py``).
- L95 `app_dir(name: str)` (function) — Where an app's code lives: its manifest's folder when this store installs
- L113 `guide(name: str)` (function) — The app's parsed ``help.md``, or None when it has none.
- L131 `summary(name: str)` (function) — The app's one sentence for staff, or '' when it has no guide.
- L137 `forget()` (function) — Drop the cache (tests that point an app at another guide).
- L142 `load_manifest(name: str)` (function) — The app's manifest instance, also for an app this store does not install
- L169 `_tree()` (function)
