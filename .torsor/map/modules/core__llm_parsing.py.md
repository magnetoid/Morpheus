---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/llm_parsing.py

Symbols in `core/llm_parsing.py`.

- L24 `parse_llm_json(raw: str)` (function) — Extract the JSON payload an LLM was asked to return.
- L76 `_outermost_block(txt: str)` (function) — Return the slice from the first '{' or '[' to the matching last '}' or ']'.
- L93 `_escape_literal_whitespace_in_strings(s: str)` (function) — Replace literal \n / \r / \t inside JSON string literals with
