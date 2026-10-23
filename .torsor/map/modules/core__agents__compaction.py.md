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

# core/agents/compaction.py

Symbols in `core/agents/compaction.py`.

- L26 `estimate_tokens(messages: list[LLMMessage])` (function) — Cheap, dependency-free token estimate (~4 chars/token).
- L36 `compact(messages: list[LLMMessage], *, soft_limit: int=DEFAULT_SOFT_LIMIT, keep_recent: int=DEFAULT_KEEP_RECENT, summarizer: Callable[[str], str] | None=None)` (function) — Return a possibly-compacted copy of ``messages``.
- L78 `_summarize(middle: list[LLMMessage], summarizer: Callable[[str], str] | None)` (function)
