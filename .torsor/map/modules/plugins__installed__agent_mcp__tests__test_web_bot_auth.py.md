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

# plugins/installed/agent_mcp/tests/test_web_bot_auth.py

Symbols in `plugins/installed/agent_mcp/tests/test_web_bot_auth.py`.

- L31 `_b64url(raw: bytes)` (function)
- L35 `_Signer` (class)
- L36 `__init__(self)` (method)
- L47 `jwks(self, *, kid: bool=True)` (method)
- L53 `headers(self, authority: str='testserver', *, created: int | None=None, expires: int | None=None, tag: str='web-bot-auth', keyid: str | None=None, agent: str=AGENT, components: tuple[str, ...]=('@authority', 'signature-agent'))` (method)
- L84 `_run(headers: dict, path: str='/mcp/storefront/v1/')` (function)
- L90 `ParsingTests` (class)
- L91 `test_thumbprint_is_rfc7638(self)` (method)
- L98 `test_signature_input_parses_components_and_params(self)` (method)
- L110 `test_agent_origin_must_be_a_public_https_host(self)` (method)
- L129 `VerifyTests` (class)
- L130 `setUp(self)` (method)
- L139 `test_a_valid_signature_attaches_the_agent(self)` (method)
- L148 `test_the_directory_is_cached(self)` (method)
- L153 `test_a_key_without_kid_matches_by_thumbprint(self)` (method)
- L157 `test_a_signature_for_another_host_is_ignored(self)` (method)
- L160 `test_expired_and_future_signatures_are_ignored(self)` (method)
- L169 `test_a_window_longer_than_a_day_is_ignored(self)` (method)
- L173 `test_the_wrong_tag_is_ignored(self)` (method)
- L176 `test_authority_must_be_covered(self)` (method)
- L179 `test_an_unknown_key_is_ignored(self)` (method)
- L182 `test_a_directory_that_cannot_be_fetched_fails_soft(self)` (method)
- L189 `test_a_failed_fetch_is_not_retried_on_every_request(self)` (method)
- L195 `test_a_non_public_agent_origin_is_never_fetched(self)` (method)
- L200 `test_a_garbled_header_is_ignored(self)` (method)
- L208 `test_requests_without_the_headers_are_untouched(self)` (method)
- L213 `test_the_agent_stamps_an_order(self)` (method)
- L234 `ManifestTests` (class)
- L235 `test_agent_json_advertises_origin_verification(self)` (method)
- L246 `DirectoryFetchTests` (class)
- L247 `test_fetch_uses_the_fixed_directory_path(self)` (method)
