---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/staff_mfa/tests/test_mfa.py

Symbols in `plugins/installed/staff_mfa/tests/test_mfa.py`.

- L20 `_staff(email='boss@example.com')` (function)
- L26 `_customer(email='shopper@example.com')` (function)
- L32 `_confirmed_device(user)` (function)
- L40 `TotpContract` (class) — Hit pyotp's real interface, not a mock.
- L43 `test_correct_code_passes_wrong_fails(self)` (method)
- L51 `test_provisioning_uri_is_otpauth(self)` (method)
- L57 `RecoveryCodes` (class)
- L58 `setUp(self)` (method)
- L61 `test_codes_are_hashed_single_use(self)` (method)
- L76 `test_regenerate_replaces_old_codes(self)` (method)
- L83 `SecondFactorSubscriber` (class) — The AUTH_SECOND_FACTOR decision — the heart of the disable/enforce logic.
- L86 `setUp(self)` (method)
- L92 `_req(self)` (method)
- L97 `test_subscriber_is_registered_on_core_hook(self)` (method)
- L101 `test_non_staff_never_gated(self)` (method)
- L105 `test_staff_without_device_optin_not_gated(self)` (method)
- L110 `test_enrolled_staff_is_challenged(self)` (method)
- L121 `EnrollPermissionBoundary` (class) — Three-way boundary on the enrollment dashboard page.
- L124 `setUp(self)` (method)
- L127 `test_anonymous_blocked(self)` (method)
- L131 `test_non_staff_blocked(self)` (method)
- L136 `test_staff_allowed(self)` (method)
- L142 `ChallengeFlow` (class) — Session-gated challenge view completes login on a valid code.
- L145 `test_no_pending_redirects_out(self)` (method)
- L149 `test_valid_totp_logs_in(self)` (method)
- L165 `test_wrong_code_does_not_log_in(self)` (method)
- L177 `SecondFactorFailClosed` (class) — otp_verify must fail CLOSED when a second-factor subscriber raises.
- L186 `test_raising_second_factor_handler_blocks_login(self)` (method)
- L214 `AdminResetCommand` (class)
- L215 `test_reset_clears_device(self)` (method)
- L228 `EnrollConfirmRateLimit` (class) — The confirm endpoint is throttled so it can't be a TOTP oracle.
- L231 `test_confirm_is_throttled(self)` (method)
