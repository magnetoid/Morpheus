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

# plugins/installed/seo/services/redirects.py

Symbols in `plugins/installed/seo/services/redirects.py`.

- L42 `normalise_path(path: str)` (function) — A comparable form of a path: no host, no query, no fragment, leading slash.
- L62 `normalise_target(target: str)` (function) — A redirect target may legitimately be an absolute URL (an off-site move)
- L76 `_compile_rules()` (function)
- L106 `_rules()` (function)
- L123 `invalidate_redirect_cache()` (function) — Drop the compiled ruleset. Called whenever a Redirect row changes.
- L137 `_match(path: str, rules: dict)` (function)
- L186 `resolve_redirect(path: str)` (function) — ``(target_path, status_code)`` for ``path``, or None.
- L209 `record_redirect_hit(path: str)` (function) — Best-effort hit counter. Never on the critical path of the response.
- L226 `collapse_chain(from_path: str, to_path: str)` (function) — Follow ``to_path`` through existing exact rules to its final destination.
- L259 `validate_redirect(*, from_path: str, to_path: str, status_code: int, match_type: str='exact')` (function) — Merchant-facing checks. Returns a list of human-readable problems.
- L299 `_blocks_homepage_redirects()` (function)
- L312 `export_redirects_csv()` (function)
- L326 `import_redirects_csv(text: str)` (function) — Upsert rules from CSV. Returns {created, updated, skipped, errors}.
- L376 `record_404(*, path: str, referrer: str='')` (function)
- L399 `suggest_redirect(path: str)` (function) — Suggest a live URL for a 404 path.
- L482 `_path_from_history(path: str)` (function) — The current path of whatever object used to live at ``path``.
- L497 `refresh_404_suggestions(*, limit: int=50)` (function) — Fill in suggested_target on the top unresolved 404s.
