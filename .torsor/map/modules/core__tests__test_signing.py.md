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

# core/tests/test_signing.py

Symbols in `core/tests/test_signing.py`.

- L27 `KeypairTests` (class)
- L28 `test_round_trip(self)` (method)
- L33 `test_a_different_payload_does_not_verify(self)` (method)
- L37 `test_a_different_key_does_not_verify(self)` (method)
- L43 `VerifyFailsClosedTests` (class)
- L44 `test_every_empty_input_is_false(self)` (method)
- L50 `test_malformed_base64_is_false_not_an_exception(self)` (method)
- L55 `test_a_library_failure_is_false_not_an_exception(self)` (method) — A caller that forgot a try/except must not end up applying an update.
- L62 `CanonicalFormTests` (class)
- L63 `test_key_order_does_not_change_the_signed_bytes(self)` (method)
- L66 `test_the_signature_field_is_excluded(self)` (method) — A document cannot contain a signature over itself.
- L71 `ManifestTests` (class)
- L72 `setUp(self)` (method)
- L76 `test_signed_manifest_verifies(self)` (method)
- L80 `test_tampering_with_any_field_breaks_it(self)` (method)
- L85 `test_an_unsigned_manifest_is_rejected(self)` (method)
- L88 `test_a_non_dict_is_rejected(self)` (method)
- L92 `SignedManifestSourceTests` (class)
- L93 `setUp(self)` (method)
- L96 `_source(self, url='https://morpheus.direct/updates/stable.json', key=None)` (method)
- L101 `_serve(self, doc)` (method) — Patch the network read so only verification is under test.
- L113 `test_a_valid_manifest_yields_the_version(self)` (method)
- L120 `test_a_tampered_manifest_is_ignored_entirely(self)` (method)
- L126 `test_no_public_key_means_no_trust(self)` (method)
- L131 `test_a_non_https_url_is_refused_before_any_request(self)` (method)
- L136 `SourceSelectionTests` (class)
- L142 `test_a_signed_manifest_wins_over_the_github_source(self)` (method) — The GitHub source proves only that we reached a server.
- L149 `test_falls_back_to_github_when_no_manifest_is_configured(self)` (method)
