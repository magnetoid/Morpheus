---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/assistant/persistence.py

Symbols in `core/assistant/persistence.py`.

- L28 `_fallback_dir()` (function)
- L41 `StoredMessage` (class)
- L54 `AssistantStore` (class) — Read/write conversation history. Always succeeds — falls back to disk.
- L57 `__init__(self, *, prefer_db: bool=True)` (method)
- L60 `append(self, *, conversation_key: str, message: StoredMessage)` (method) — Append a message. `conversation_key` is e.g. user pk or 'session:abc'.
- L68 `history(self, *, conversation_key: str, limit: int=30)` (method)
- L77 `_db_append(self, key: str, m: StoredMessage)` (method)
- L101 `_db_history(self, key: str, limit: int)` (method)
- L133 `_file_path(self, key: str)` (method)
- L137 `_file_append(self, key: str, m: StoredMessage)` (method)
- L144 `_file_history(self, key: str, limit: int)` (method)
- L165 `get_default_store()` (function)
