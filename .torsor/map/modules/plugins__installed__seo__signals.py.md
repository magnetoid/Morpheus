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

# plugins/installed/seo/signals.py

Symbols in `plugins/installed/seo/signals.py`.

- L27 `wire()` (function) — Connect every receiver.
- L61 `_on_redirect_saved(sender, instance=None, **kwargs)` (function)
- L67 `_on_index_policy_changed(sender, instance=None, **kwargs)` (function)
- L74 `_wire_slug_watchers()` (function) — Watch the models whose slug IS a public URL.
- L90 `_model_for(label: str)` (function)
- L101 `_on_slug_maybe_changed(sender, instance=None, **kwargs)` (function) — Record the old public path when a slug changes.
- L125 `_on_template_changed(sender, instance=None, **kwargs)` (function) — A pattern edit must re-title its pages on the NEXT render, not when the
