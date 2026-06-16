---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/assistant/persistence.py

Symbols in `core/assistant/persistence.py`.

- L29 `_fallback_dir()` (function)
- L42 `StoredMessage` (class)
- L55 `AssistantStore` (class) — Read/write conversation history. Always succeeds — falls back to disk.
- L58 `__init__(self, *, prefer_db: bool=True)` (method)
- L61 `append(self, *, conversation_key: str, message: StoredMessage)` (method) — Append a message. `conversation_key` is e.g. user pk or 'session:abc'.
- L69 `history(self, *, conversation_key: str, limit: int=30)` (method)
- L78 `_db_append(self, key: str, m: StoredMessage)` (method)
- L109 `_db_history(self, key: str, limit: int)` (method)
- L141 `_file_path(self, key: str)` (method)
- L145 `_file_append(self, key: str, m: StoredMessage)` (method)
- L152 `_file_history(self, key: str, limit: int)` (method)
- L173 `get_default_store()` (function)
