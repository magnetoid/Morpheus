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

# core/tests/test_net_egress.py

Symbols in `core/tests/test_net_egress.py`.

- L24 `_resolves_to(addr: str)` (function) — Patch getaddrinfo so a hostname resolves to `addr`.
- L29 `PublicIpTests` (class)
- L30 `test_public_addresses_pass(self)` (method)
- L36 `test_internal_ranges_are_refused(self)` (method)
- L52 `HostResolutionTests` (class)
- L53 `test_literal_internal_ip_refused_without_dns(self)` (method)
- L57 `test_hostname_resolving_internally_is_refused(self)` (method)
- L62 `test_hostname_resolving_publicly_passes(self)` (method)
- L66 `test_every_returned_address_must_be_public(self)` (method)
- L72 `test_resolution_failure_is_TRANSIENT_not_permanent(self)` (method) — A DNS blip must be distinguishable from a genuinely unsafe host.
- L90 `test_unresolvable_is_a_subclass_so_base_catches_still_work(self)` (method)
- L95 `test_empty_host_refused(self)` (method)
- L99 `CheckOutboundUrlTests` (class)
- L100 `test_scheme_enforced(self)` (method)
- L111 `test_metadata_endpoint_refused(self)` (method)
- L115 `test_ipv6_brackets_are_stripped_before_the_check(self)` (method)
- L121 `test_non_raising_helper(self)` (method)
