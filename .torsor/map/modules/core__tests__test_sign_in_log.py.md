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

# core/tests/test_sign_in_log.py

Symbols in `core/tests/test_sign_in_log.py`.

- L27 `sign_in_with_code(client, email, **headers)` (function)
- L35 `SignInLogTests` (class)
- L36 `setUp(self)` (method)
- L41 `test_a_code_sign_in_records_time_address_and_device(self)` (method)
- L54 `test_a_password_sign_in_is_recorded(self)` (method)
- L60 `test_a_wrong_password_records_nothing(self)` (method)
- L64 `test_the_cloudflare_address_beats_a_forged_forwarded_for(self)` (method)
- L74 `test_only_this_persons_sign_ins_are_listed(self)` (method)
- L81 `test_the_ten_newest_are_listed_newest_first(self)` (method)
- L96 `test_prune_drops_sign_ins_older_than_90_days_and_nothing_else(self)` (method)
- L112 `DescribeDeviceTests` (class)
- L113 `test_common_browsers_and_devices(self)` (method)
