# Newsletter app (under Marketing)

## Context

A merchant wants a powerful newsletter system — email capture via popups,
a managed subscriber list, and newsletter sends. Audit of the existing platform
(required before any new plugin) shows the pieces are **partly** there:

- `marketing.EmailCampaign` already owns newsletter **sending** (draft →
  schedule → sent, open/click counts). **Do not duplicate it** (the PR #62
  parallel-table lesson).
- `consent` owns **cookie** banners (not marketing signup popups).
- `cms` Form supports a `newsletter` form type; `customers` has a `newsletter`
  preference; `crm` has a `newsletter signup` lead source.

**Genuinely missing — what this plugin owns:**
1. A first-class **subscriber list with double opt-in** (no dedicated
   `NewsletterSubscriber` model exists today).
2. **Marketing signup popups** (exit-intent / timed / scroll) that capture
   emails into that list — distinct from cookie consent.

## Boundary (one concept = one owner)

| Concept | Owner | This plugin's relation |
|---|---|---|
| Subscriber list + double opt-in | **newsletter** (new) | owns `NewsletterSubscriber` |
| Signup popups | **newsletter** (new) | owns `SignupPopup` |
| Email *sending* / campaigns | `marketing.EmailCampaign` | **reuse** (Phase 3 targets a campaign at the list) |
| Confirm / welcome emails | core email registry | `contribute_email_templates()` |
| Cookie consent | `consent` | untouched |

`newsletter` declares `requires = ['marketing']` so Phase-3 sends can reference
`EmailCampaign` without a parallel sender. Everything lives under
`plugins/installed/newsletter/`; nav + settings file under the **marketing**
section.

## Models (Phase 1)

```
NewsletterSubscriber
  email (unique, indexed) · status: pending|confirmed|unsubscribed
  customer FK (nullable) · source: popup|form|checkout|manual|import
  confirm_token (opaque) · tags (JSON, segmentation)
  confirmed_at · unsubscribed_at · created_at · updated_at

SignupPopup
  name · enabled · headline · body · button_label · success_message
  trigger: immediate|time_delay|exit_intent|scroll_depth · trigger_value
  frequency: once|daily|every_visit · incentive · coupon_code
  audience: all|new|returning · impressions · conversions · timestamps
```

## Surfaces & phases (each independently shippable)

- **Phase 1 — foundation (this PR):** plugin scaffold (manifest, apps, register
  in `MORPHEUS_DEFAULT_PLUGINS`), the two models + migration, a double-opt-in
  service (`subscribe(email, source) → pending + confirm email`;
  `confirm(token) → confirmed`; `unsubscribe(token)`), the `newsletter_confirm`
  + `newsletter_welcome` email templates via `contribute_email_templates()`,
  and the public `/newsletter/subscribe/` + `/newsletter/confirm/<token>/`
  endpoints. Tests for the opt-in lifecycle.
- **Phase 2 — capture UI:** `StorefrontBlock(slot='global_below_body')` popup
  with JS triggers (exit-intent/timed/scroll, frequency cap via localStorage)
  posting to the subscribe endpoint; dashboard pages (subscribers list w/
  filters + export, popup CRUD) under `section='marketing'`; `SettingsPanel`
  (category='marketing').
- **Phase 3 — sending + Linda:** "Send to subscribers" by targeting a
  `marketing.EmailCampaign` at confirmed subscribers (reuse, no new sender);
  `contribute_agent_tools()` so Linda operates it
  (`newsletter.subscriber_count`, `newsletter.list_subscribers`,
  `newsletter.create_popup`, `newsletter.toggle_popup`,
  `newsletter.broadcast`); popup impression/conversion analytics.

## Safety / conventions
- Double opt-in (GDPR-friendly): a subscriber is only mailable at `confirmed`.
- Unsubscribe link in every send; `unsubscribed` is terminal.
- Migration created via `manage.py makemigrations` (the no-migration-writes hook
  blocks hand-editing); CI applies it on real Postgres.
- Disable-test: removing the plugin removes its nav, popups (storefront block),
  settings, and agent commands.

## Verification
`manage.py check` + `makemigrations --check`; opt-in lifecycle unit tests
(`subscribe → pending`, `confirm → confirmed`, double-confirm idempotent,
`unsubscribe → unsubscribed`); endpoint tests; smoke `/newsletter/confirm/...`.
