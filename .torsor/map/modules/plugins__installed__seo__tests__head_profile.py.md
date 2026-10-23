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

# plugins/installed/seo/tests/head_profile.py

Symbols in `plugins/installed/seo/tests/head_profile.py`.

- L61 `_norm(value: str)` (function)
- L65 `_HeadParser` (class) — Collect title / meta / link / JSON-LD from the document head.
- L68 `__init__(self)` (method)
- L79 `handle_starttag(self, tag, attrs)` (method)
- L105 `handle_endtag(self, tag)` (method)
- L115 `handle_data(self, data)` (method)
- L120 `_jsonld_summary(raw_blocks: list[str])` (function) — Reduce every JSON-LD block to {type, id, props} entries.
- L184 `_scalar(value)` (function)
- L188 `head_profile(html: str, *, path: str='', status: int=200)` (function) — Return the SEO-relevant shape of a rendered page.
- L211 `robots_directives(value: str)` (function) — `index, follow, max-snippet:-1` → an order-insensitive directive set.
- L216 `diff_profiles(before: dict, after: dict)` (function) — Human-readable regressions of `after` against the recorded `before`.
- L281 `_group_by_type(nodes: list[dict])` (function) — Index nodes by type, counting a MULTI-typed node under each of its types.
- L299 `_type_names(value)` (function)
