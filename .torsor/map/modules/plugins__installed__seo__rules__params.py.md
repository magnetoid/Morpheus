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

# plugins/installed/seo/rules/params.py

Symbols in `plugins/installed/seo/rules/params.py`.

- L65 `ParamDecision` (class) — What the query string means for this URL.
- L75 `noindex(self)` (method)
- L79 `decide_params(query: str, *, paginated: bool=False)` (function) — Apply the index rules to a raw query string.
- L132 `blocked_param_patterns()` (function) — robots.txt `Disallow` patterns for every parameter policied `block`.
- L158 `captures_reserved(param: str)` (function) — Would a rule named `param` apply to a parameter the platform reserves?
- L166 `invalidate_index_rules_cache()` (function) — Drop the compiled ruleset. Hangs off post_save/post_delete.
- L177 `_rules()` (function)
- L194 `_compile()` (function) — `{'exact': {param: (policy, frozenset)}, 'wildcards': [(prefix, policy, frozenset)]}`.
- L232 `_legacy_noindex_params()` (function) — `SiteSeoSettings.noindex_query_params` as implicit no-index rules.
- L247 `_rule_for(param: str, rules: dict)` (function)
- L257 `_normalise(pairs: list[tuple[str, str]])` (function) — Sorted, de-duplicated, re-encoded.
- L262 `_consolidate_unlisted()` (function) — What happens to a parameter no rule mentions.
