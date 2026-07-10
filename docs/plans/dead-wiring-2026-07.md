# Dead-wiring audit — findings & disposition (2026-07-10)

Second audit sweep (dead subscribers, orphan tasks, unrendered slots, inert
config). The order-lifecycle bugs are fixed in the same batch as this doc; the
rest is tracked here with a disposition each.

## Fixed (this batch)

- **ORDER_FULFILLED / ORDER_CANCELLED never fired** → shipment + cancellation
  emails never sent, stock reservations never released on cancel, affiliate
  clawback + refund pixel dead. Root cause: the FSM transitions
  (`fulfill`/`cancel`) are invoked from many call sites (dashboard, agent
  tools, GraphQL, marketplace) and none fired the hook. Fixed centrally with a
  `post_transition` receiver in `orders/signals.py` — a new call site can't
  re-break it. (`orders/tests/test_fsm_hooks.py`.)
- **PAYMENT_REFUNDED never fired** — `RefundService.process` fired the string
  `'refund.processed'`, which had zero subscribers, while the refund email,
  affiliate clawback, and conversion pixel all listened on PAYMENT_REFUNDED.
  Switched the fire to the canonical event. (`orders/tests/test_refunds.py`.)

## Deferred — needs a product decision (not a pure bug)

- **PRODUCT_CALCULATE_PRICE filter is never invoked.** Subscribers exist
  (ai_assistant dynamic pricing, functions) but both are **default-off**, so a
  default store has no active bug. Wiring it correctly requires deciding where
  the filter applies: the one clean choke point for money charged is
  `orders/services.py:_resolve_unit_price` (cart line), but applying it there
  alone makes the charged price diverge from the displayed catalog price
  (`catalog.Product.display_price`, storefront serializers). Consistent
  display-and-charge integration + rounding/per-currency behaviour is a
  merchandising decision. Do NOT half-wire the money path. When specced: run
  the filter at both the display serializer and `_resolve_unit_price`, with a
  test asserting shelf price == cart price under an active strategy.

## Deferred — invisible storefront slots (theme decision)

Plugins contribute `StorefrontBlock(slot=…)` to slots the active `dot_books`
theme never renders, so those surfaces are invisible until the theme adds a
`{% storefront_blocks "<slot>" %}` tag (or the plugins move to a rendered slot):

- `global_head` — brand_kit CSS tokens + motion CSS never load (add before
  `</head>` in `base.html`).
- `checkout_extra` — post_checkout_upsell, referrals, checkout_experience,
  discovery_quiz, smart_shipping, rails (checkout_one_page.html).
- `account_summary_extra` — referrals, returns_portal, subscriptions_plus
  (account_home.html; or move to `ACCOUNT_SUMMARY_FIELDS`).
- `pdp_below_gallery` — media_3d (3D/AR viewer), ugc_reviews (product_detail).
- `order_receipt_extra` (post_checkout_upsell), `auth_login_extra` (staff_sso).

These are theme-template additions; batch them into one theme pass with visual
review rather than blind-adding tags.

## Deferred — half-built default plugins (decide: finish, gate, or drop)

Several plugins ship in `MORPHEUS_DEFAULT_PLUGINS` but read few/none of their
own config keys and contribute only to invisible slots — they read as stubs:

- `referrals` — reads **none** of its 7 config keys (reward amounts,
  anti-fraud, contest); no reward-issuing backend. Merchants configure rewards
  that never apply.
- Schema-only (inert) keys elsewhere: `checkout_experience.show_address_autocomplete`,
  `smart_shipping.enable_easypost/enable_shippo`,
  `returns_portal.store_credit_bonus_pct`, `ugc_reviews.creator_stipend_*`,
  `subscriptions_plus.loyalty_points_multiplier/swap_window_days/churn_save_prompt`.

Each: wire the key to behaviour, or remove it from the schema so the settings
UI stops offering a toggle that does nothing.

## Deferred — low severity

- **Dead event constants** (never fired, never subscribed): `PAYMENT_FAILED`
  (notable — payments handles failure but emits no platform event, so nothing
  can react), `AI_DESCRIPTION_GENERATED`, `AI_RECOMMENDATION_REQUESTED`,
  `CART_CREATED`, `CART_UPDATED`. Remove or wire.
- **Orphan Celery task** `ai_assistant.tasks.reembed_all_products` — no trigger
  path (no beat entry, no caller, no command). Add a management command /
  dashboard button, or drop.
- **`PAYMENT_CAPTURED` subscriber** (`orders/plugin.py`) has no fire site;
  harmless (the paid path reaches `confirm_order` via ORDER_PAID) but the
  registration is misleading. Delete or fire it.
- Promote the module-local `'collection.updated'` string
  (`catalog/signals.py`) to a typed `MorpheusEvents` constant.
