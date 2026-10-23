---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/payments/tests/test_delegated_token.py

Symbols in `plugins/installed/payments/tests/test_delegated_token.py`.

- L25 `_order()` (function)
- L33 `RedeemDelegatedTokenSuccessTests` (class)
- L34 `test_success_records_transaction_and_sends_off_session_confirm(self)` (method)
- L78 `test_missing_acp_metadata_falls_back_to_order_scoped_key(self)` (method)
- L93 `test_modify_failure_never_poisons_the_charge(self)` (method)
- L111 `test_zero_decimal_currency_sends_whole_units(self)` (method)
- L130 `RedeemDelegatedTokenDeclineTests` (class)
- L131 `test_card_error_records_failed_tx_with_decline_code(self)` (method)
- L153 `test_card_error_without_user_message_never_leaks_str(self)` (method)
- L165 `test_connection_error_is_retryable_with_no_transaction_row(self)` (method)
- L184 `test_generic_stripe_error_returns_fixed_message_and_logs_raw(self)` (method)
- L198 `test_processing_intent_records_pending_and_is_retryable(self)` (method)
- L223 `test_non_succeeded_status_treated_as_authentication_decline(self)` (method)
