---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/agent_mcp/web_bot_auth.py

Symbols in `plugins/installed/agent_mcp/web_bot_auth.py`.

- L57 `VerifiedBot` (class)
- L65 `_b64url_decode(value: str)` (function)
- L70 `_b64url(raw: bytes)` (function)
- L74 `jwk_thumbprint(jwk: dict)` (function) — RFC 7638 thumbprint of an OKP key: SHA-256 over the canonical JSON of
- L88 `_split_top_level(value: str, sep: str)` (function) — Split on ``sep`` outside quoted strings and parentheses.
- L121 `_unquote(value: str)` (function)
- L130 `_parse_params(parts: list[str])` (function)
- L149 `_parse_dictionary(value: str)` (function) — ``a=..., b=...`` → {label: raw member text}.
- L163 `parse_signature_input(value: str)` (function) — One ``Signature-Input`` member → (label, components, params, raw).
- L197 `parse_signature(value: str, label: str)` (function) — The ``Signature`` member for ``label`` → raw signature bytes.
- L211 `agent_origin(header_value: str)` (function) — ``Signature-Agent`` → ``https://host[:port]`` when it names a public
- L226 `_parse_agent_origin(header_value: str)` (function)
- L251 `_fetch_jwks(origin: str)` (function) — GET the agent's key directory (fixed path, https only, size-capped).
- L284 `_fetch_budget_ok()` (function)
- L296 `directory_keys(origin: str)` (function) — The agent's JWKS keys, cached per origin; [] when unavailable.
- L315 `_public_key(keys: list[dict], keyid: str)` (function)
- L346 `_component_value(request, name: str)` (function)
- L358 `verify_request(request)` (function) — The agent that signed this request, or None. Never raises.
