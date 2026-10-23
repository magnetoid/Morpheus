---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/agent_core/approvals.py

Symbols in `plugins/installed/agent_core/approvals.py`.

- L28 `resolve(tool_name: str, args: dict, context: dict)` (function) — True iff an approved, unconsumed, unexpired request matches this exact
- L62 `record_pending(agent=None, tool=None, run_id=None, arguments=None, context=None, **kwargs)` (function) — Record a pending approval request + pause the run. Idempotent: only one
- L97 `register()` (function) — Wire the resolver into the kernel seam + subscribe the recorder.
