---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/errors/services.py

Symbols in `core/errors/services.py`.

- L16 `_scrub(text: str)` (function)
- L25 `_fingerprint_server(exc: BaseException)` (function) — Stable hash from exception class + first 3 frame file:line pairs.
- L40 `_fingerprint_client(message: str, source_url: str, lineno: int)` (function) — Stable hash for a JS error — message + file:line.
- L47 `_ip_hash(request)` (function)
- L65 `_truncate(text: str, limit: int)` (function) — Cap `text` at `limit` chars with a visible marker so readers know
- L74 `record_error(exc: BaseException, *, request=None, kind: str='server', level: str='error', extra: dict[str, Any] | None=None)` (function) — Write a server-side exception to the error log. Fail-soft.
- L114 `record_client_error(payload: dict[str, Any], *, request=None)` (function) — Write a JS error received from the browser. Validates payload shape.
