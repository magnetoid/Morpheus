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

# core/errors/services.py

Symbols in `core/errors/services.py`.

- L39 `redact_secrets(text: str)` (function)
- L47 `_scrub(text: str)` (function)
- L57 `_fingerprint_server(exc: BaseException)` (function) — Stable hash from exception class + first 3 frame file:line pairs.
- L85 `stable_text(text: str)` (function) — ``text`` with its per-occurrence parts replaced, for fingerprinting only.
- L92 `_fingerprint_client(message: str, source_url: str, lineno: int)` (function) — Stable hash for a JS error — message + file:line.
- L99 `_ip_hash(request)` (function)
- L117 `_truncate(text: str, limit: int)` (function) — Cap `text` at `limit` chars with a visible marker so readers know
- L126 `_with_context(meta: dict[str, Any] | None, request=None)` (function) — Add the request context to an event's metadata while detailed capture is on.
- L144 `record_error(exc: BaseException, *, request=None, kind: str='server', level: str='error', extra: dict[str, Any] | None=None)` (function) — Write a server-side exception to the error log. Fail-soft.
- L186 `_user_of(request)` (function)
- L191 `record_message(message: str, *, level: str='error', kind: str='server', source: str='', exception_class: str='', stack_trace: str='', extra: dict[str, Any] | None=None, request=None)` (function) — Write a server-side error from a pre-formatted message/stack when there is
- L250 `throttled(key: str)` (function) — True when ``key`` was recorded in this process within the last minute.
- L276 `record_http(source: str, *, request, status: int, duration_ms: int, message: str)` (function) — Record a request-level event (detailed capture). Throttled and fail-soft.
- L330 `is_client_noise(name: str, message: str)` (function)
- L334 `record_client_error(payload: dict[str, Any], *, request=None)` (function) — Write a JS error received from the browser. Validates payload shape.
