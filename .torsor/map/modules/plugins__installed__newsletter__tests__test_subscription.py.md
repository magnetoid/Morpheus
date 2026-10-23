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

# plugins/installed/newsletter/tests/test_subscription.py

Symbols in `plugins/installed/newsletter/tests/test_subscription.py`.

- L14 `OptInLifecycleTests` (class)
- L15 `test_subscribe_creates_pending_and_sends_confirm(self)` (method)
- L23 `test_confirm_flips_to_confirmed_and_welcomes(self)` (method)
- L31 `test_confirm_is_idempotent(self)` (method)
- L40 `test_already_confirmed_subscribe_does_not_resend(self)` (method)
- L47 `test_unsubscribe_is_terminal(self)` (method)
- L54 `test_invalid_email_rejected(self)` (method)
- L60 `test_confirm_unknown_token_is_none(self)` (method)
- L64 `PluginContributionTests` (class)
- L65 `test_contributes_email_templates(self)` (method)
- L71 `EndpointTests` (class)
- L72 `test_subscribe_endpoint_returns_json(self)` (method)
- L80 `test_subscribe_endpoint_rejects_bad_email(self)` (method)
- L85 `test_confirm_endpoint(self)` (method)
