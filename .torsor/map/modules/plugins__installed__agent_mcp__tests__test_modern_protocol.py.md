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

# plugins/installed/agent_mcp/tests/test_modern_protocol.py

Symbols in `plugins/installed/agent_mcp/tests/test_modern_protocol.py`.

- L32 `_headers(method: str, name: str | None=None, version: str=VERSION, **extra)` (function)
- L44 `_body(method: str, params: dict | None=None, _id=1, meta: dict | None=None)` (function)
- L53 `_post(body: str, headers: dict, token: str='')` (function)
- L59 `DiscoverTests` (class)
- L60 `test_server_discover_answers_with_versions_capabilities_and_identity(self)` (method)
- L75 `test_discover_also_answers_a_legacy_probe_without_headers(self)` (method)
- L85 `ResultShapeTests` (class)
- L86 `test_tools_list_is_cacheable_and_deterministic(self)` (method)
- L98 `test_resources_list_and_read_are_cacheable(self)` (method)
- L105 `test_a_notification_is_accepted_with_no_body(self)` (method)
- L110 `test_a_modern_request_never_gets_a_session(self)` (method)
- L118 `test_batches_are_not_accepted_in_the_modern_era(self)` (method)
- L127 `ValidationTests` (class)
- L128 `test_a_method_header_that_disagrees_with_the_body_is_a_header_mismatch(self)` (method)
- L133 `test_tools_call_without_mcp_name_is_a_header_mismatch(self)` (method)
- L141 `test_a_version_header_that_disagrees_with_meta_is_a_header_mismatch(self)` (method)
- L146 `test_a_base64_sentinel_name_is_decoded_before_comparison(self)` (method)
- L156 `test_an_unsupported_version_lists_the_supported_ones(self)` (method)
- L165 `test_missing_client_capabilities_is_invalid_params(self)` (method)
- L171 `test_unknown_methods_are_404_in_the_modern_era(self)` (method)
- L178 `test_a_foreign_origin_is_refused(self)` (method)
- L183 `ToolCallTests` (class)
- L184 `setUp(self)` (method)
- L194 `_call(self, name: str, arguments: dict | None=None, token: str='tok-cat')` (method)
- L201 `test_a_modern_call_returns_a_complete_result(self)` (method)
- L209 `test_a_tool_failure_is_an_error_result_not_a_legacy_code(self)` (method)
- L220 `test_authentication_errors_use_a_code_outside_the_reserved_range(self)` (method)
- L227 `LegacyEraTests` (class)
- L228 `test_initialize_still_negotiates_the_legacy_version(self)` (method)
- L238 `test_legacy_results_keep_their_shape(self)` (method)
