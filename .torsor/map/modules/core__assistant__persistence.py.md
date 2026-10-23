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

# core/assistant/persistence.py

Symbols in `core/assistant/persistence.py`.

- L29 `_fallback_dir()` (function)
- L42 `StoredMessage` (class)
- L59 `AssistantStore` (class) — Read/write conversation history. Always succeeds — falls back to disk.
- L62 `__init__(self, *, prefer_db: bool=True)` (method)
- L65 `append(self, *, conversation_key: str, message: StoredMessage)` (method) — Append a message. `conversation_key` is e.g. user pk or 'session:abc'.
- L73 `history(self, *, conversation_key: str, limit: int=30)` (method)
- L82 `_db_append(self, key: str, m: StoredMessage)` (method)
- L116 `_db_history(self, key: str, limit: int)` (method)
- L148 `_file_path(self, key: str)` (method)
- L152 `_file_append(self, key: str, m: StoredMessage)` (method)
- L159 `_file_history(self, key: str, limit: int)` (method)
- L180 `get_default_store()` (function)
