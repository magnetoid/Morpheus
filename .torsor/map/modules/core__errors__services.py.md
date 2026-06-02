---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/errors/services.py

Symbols in `core/errors/services.py`.

- L15 `_scrub(text: str)` (function)
- L23 `_fingerprint_server(exc: BaseException)` (function) — Stable hash from exception class + first 3 frame file:line pairs.
- L38 `_fingerprint_client(message: str, source_url: str, lineno: int)` (function) — Stable hash for a JS error — message + file:line.
- L45 `_ip_hash(request)` (function)
- L63 `_truncate(text: str, limit: int)` (function) — Cap `text` at `limit` chars with a visible marker so readers know
- L72 `record_error(exc: BaseException, *, request=None, kind: str='server', level: str='error', extra: dict[str, Any] | None=None)` (function) — Write a server-side exception to the error log. Fail-soft.
- L107 `record_client_error(payload: dict[str, Any], *, request=None)` (function) — Write a JS error received from the browser. Validates payload shape.
