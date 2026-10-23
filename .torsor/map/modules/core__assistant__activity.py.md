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

# core/assistant/activity.py

Symbols in `core/assistant/activity.py`.

- L95 `hooks_config(progress_path: Path)` (function) — The config.yaml block that makes Janus report each step to ``progress_path``.
- L107 `_humanise(name: str)` (function)
- L112 `_store_tools()` (function) — Every store tool, the way the MCP edge builds its catalogue (core only).
- L120 `_sanitised(name: str)` (function)
- L124 `ProgressReader` (class) — Reads what the hook wrote since the last read, as chat events.
- L127 `__init__(self, path: Path)` (method)
- L136 `reset(self)` (method) — Start the turn with an empty file, so no step from the last turn replays.
- L143 `read(self)` (method)
- L164 `_events(self, rec: dict)` (method)
- L192 `_model_events(self, rec: dict)` (method) — A model call (her words and the running token count) or a failed one.
- L214 `_close(self, tool: str, call: str)` (method)
- L221 `_describe(self, tool: str, args: Any)` (method)
- L230 `_describe_store(self, suffix: str)` (method)
- L257 `_plan(rec: dict)` (function)
