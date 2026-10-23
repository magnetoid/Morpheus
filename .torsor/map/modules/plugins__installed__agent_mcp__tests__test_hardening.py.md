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

# plugins/installed/agent_mcp/tests/test_hardening.py

Symbols in `plugins/installed/agent_mcp/tests/test_hardening.py`.

- L26 `_rpc(method, params=None, _id=1)` (function)
- L30 `ResourcesReadGovernanceTests` (class)
- L31 `setUp(self)` (method)
- L47 `_read(self, uri, token=None)` (method)
- L56 `test_read_without_bearer_is_unauthenticated(self)` (method)
- L60 `test_underscoped_token_cannot_read_resource(self)` (method)
- L68 `test_correctly_scoped_token_reads_resource(self)` (method)
- L76 `test_unknown_resource_uri_is_rejected(self)` (method)
- L81 `TrustedAgentOriginLockTests` (class) — The X-Verified-Agent-* headers must be ignored unless the request also
- L85 `_run(self, meta)` (method)
- L102 `test_headers_ignored_when_secret_unconfigured(self)` (method)
- L106 `test_headers_ignored_when_secret_mismatches(self)` (method)
- L116 `test_headers_trusted_with_matching_secret(self)` (method)
