---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/installed/workflows/engine.py

Symbols in `plugins/installed/workflows/engine.py`.

- L50 `register_hook_listeners(plugin)` (function)
- L56 `_make_listener(event_name: str)` (function)
- L65 `_dispatch(event_name: str, payload: dict)` (function)
- L77 `run_workflow(workflow, payload: dict, *, dry_run: bool=False)` (function) — Evaluate condition + execute actions. Persists a WorkflowRun row.
- L144 `_resolve_path(payload: Any, path: str)` (function) — Dotted lookup over dicts + objects. Missing → None.
- L157 `_resolve(value: Any, payload: Any)` (function) — If `value` is a string, treat it as a dotted path. Otherwise return as-is.
- L173 `_eval(node: Any, payload: Any)` (function) — Recursive condition evaluator. Returns False on malformed input.
- L228 `_serialize_payload(payload: dict)` (function) — Best-effort JSON-safe snapshot. Anything not serialisable becomes a stringified placeholder.
- L244 `_action_notify_staff(spec: dict, payload: dict)` (function) — spec: {kind: notify_staff, title, body?, action_url?, icon?, kind_tag?}
- L260 `_action_add_order_note(spec: dict, payload: dict)` (function) — spec: {kind: add_order_note, note}
- L279 `_action_tag_customer(spec: dict, payload: dict)` (function) — spec: {kind: tag_customer, tag}.
- L309 `_action_webhook_post(spec: dict, payload: dict)` (function) — spec: {kind: webhook_post, url, body?, headers?}
- L327 `_action_agent_skill(spec: dict, payload: dict)` (function) — spec: {kind: agent_skill, agent, message, context?}.
