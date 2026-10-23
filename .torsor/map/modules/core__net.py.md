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

# core/net.py

Symbols in `core/net.py`.

- L48 `UnsafeUrlError` (class) — Raised when a URL is refused by the egress gate.
- L52 `UnresolvableHostError` (class) — The host could not be resolved — refused, but TRANSIENTLY.
- L68 `is_public_ip(ip)` (function) — True iff `ip` is a routable public address.
- L82 `is_safe_remote_host(host: str)` (function) — True iff `host` resolves ONLY to public, routable addresses.
- L114 `resolves_safely(host: str)` (function) — Non-raising form of :func:`is_safe_remote_host` — an unresolvable host
- L124 `check_outbound_url(url: str, *, field: str='url', require_https: bool=True)` (function) — Validate `url` for a server-initiated fetch; return the host.
- L144 `is_safe_outbound_url(url: str, *, require_https: bool=True)` (function) — Non-raising form of :func:`check_outbound_url`.
- L153 `outbound_request(method: str, url: str, *, require_https: bool=True, field: str='url', **kwargs)` (function) — Send a server-initiated request to a URL someone entered (staff, an
