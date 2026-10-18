# Defects found while writing the help guides (2026-10)

Writing a guide for each of the 113 apps meant reading each app's code against what it claims. Eight
writers read them in parallel, and each claim was checked against the code before its guide landed.

**Nothing below is fixed in this release.** Each guide says plainly what its app does today, so none of
these defects is described as working. Paths are under `plugins/installed/` unless they start with
`core/`.

## Broken for staff or shoppers today

### Settings and emails

- **post_purchase:** the tracking, delivered, review-request and survey emails are never sent.
  - Their sender, `process_due_steps`, is scheduled nowhere (`post_purchase/tasks.py:25`), though its own docstring says every 15 minutes.
  - Its settings page shows no fields: the schema isn't wrapped in `properties` (`post_purchase/app.py:61-108`).
- **fraud_rules:** the settings page shows no fields (flat schema, `fraud_rules/app.py:22-51`).
  - The card-number denylist and the thresholds can't be set.
  - No screen shows an order's fraud score; only a score of 60 or more writes one log line (`fraud_rules/handlers.py:28-35`).
- **trust_signals:** the settings page shows no fields (flat schema, `trust_signals/app.py:51-98`). The signals run on built-in defaults.
- **marketing:** the coupons and campaigns table prints the row's whole text in every column (`marketing/templates/marketing/dashboard/list.html:11`). The sidebar's Coupons link goes to admin_dashboard's own, working coupon editor.
- **marketing + newsletter:** no screen, mutation or tool creates or edits an email campaign's content.
  - `EmailCampaign` is never constructed (`marketing/models.py:105-132`).
  - Newsletter's Campaigns page links "create" and "edit" to that broken table (`newsletter/templates/newsletter/dashboard/campaigns.html:15,63`).
- **promotions:**
  - The page tells merchants to create a promotion "via Linda or the Django admin" (`promotions/templates/promotions/index.html:29`). The Django admin is mounted only under `DEBUG`.
  - Linda can only create percent-off promotions (`promotions/agent_tools.py:35-81`).
- **coupons stop working if promotions is switched off:** `marketing.Coupon`'s discount maths runs inside promotions' handler (`promotions/app.py:90-133`).

### Money and orders

- **agentic_checkout:** no outside agent can be let in.
  - The API-tokens page's "ACP · checkout" box writes `mcp_scopes` (`agent_mcp/dashboard.py:314`).
  - Checkout's auth reads `acp_scopes` (`agentic_checkout/auth.py:29-42`), which only test fixtures write.
- **payments:**
  - **Bank transfer is never offered.** The `manual` gateway needs written instructions that no screen saves (`payments/gateways/manual_gateway.py:14-21`).
  - **A refund can move no money without saying so.** On a cash-on-delivery, manual or sandbox order it is recorded, and the staff member is told nothing (`payments/app.py:144-152`).
  - **"Mark paid" fires `ORDER_PAID` but not `PAYMENT_CAPTURED`** (`admin_dashboard/views_split/orders.py:281`).
- **orders (Linda's tools):**
  - `orders.add_note` reads and writes a `notes` field that `Order` doesn't have, and raises on the direct path (`orders/agent_tools.py:457-482`).
  - `orders.get` reports tax, shipping and discount as blank, because it reads the wrong field names (`orders/agent_tools.py:178-180`).
- **subscriptions:**
  - The dashboard reads `s.status`, but the field is `state`, so every status pill is blank (`subscriptions/templates/subscriptions/dashboard.html:67`).
  - The product page's "Subscribe & save" block waits on `product.subscription_eligible`, which exists nowhere (`subscriptions/templates/subscriptions/blocks/subscribe_save.html:1`).
  - The paid signup page says "% off books at checkout" on every store (`subscriptions/templates/subscriptions/subscribe.html:10`).
- **booking_marketplace:** no payment step exists in booking or stays (`booking_marketplace/stays.py:175`), and `BOOKING_ENQUIRY_MODE` is never read.
- **shipping:**
  - Free-over, weight-tier and order-total-tier rates can't be completed, because `free_threshold` and `tiers` are never saved (`shipping/dashboard.py:200-253`).
  - The "Apply tax to shipping cost" box has no reader (`shipping/dashboard.py:114`).
  - New rates are always created in USD (`shipping/dashboard.py:215`).
- **smart_shipping:** its second rate list at checkout changes nothing (`smart_shipping/templates/smart_shipping/blocks/rate_list.html:3,10`).
  - Its radio button is named `shipping_rate`, but checkout reads `shipping_rate_id`.
  - Its carbon badge can never show.
- **b2b:**
  - Bulk-order account pricing looks up `Account.customer_email`, which doesn't exist, and the error is swallowed (`b2b/views_bulk_order.py:83-86`).
  - Price lists, quotes and net terms reach no charge, and nothing links a price list to an account.
- **markets:**
  - `price_for` has no callers (`markets/services.py:55`), so market prices change nothing.
  - The edit page still says "+10% bumps every product 10%" (`markets/templates/markets/edit.html:58`).
- **cjdropshipping:** a late CJ webhook can flip a cancelled supplier order back to shipped (`cjdropshipping/services/orders.py:250-266`, `services/webhooks.py:58-70`). AliExpress has the same pattern (`aliexpress/services/orders.py:230-254`), but it isn't currently reachable.

### Content, catalogue and screens

- **localization:**
  - The Translations page is always empty: it reads `t.language`, but the field is `language_code`, and the error is swallowed (`localization/views.py:41-46`).
  - The Languages page saves a list nothing reads.
- **reviews:**
  - A merchant's reply is saved but shown nowhere (`reviews/dashboard.py:103-105`).
  - Moderation can take ten minutes to reach the storefront, because of a cache keyed on `product.updated_at`.
- **inventory:**
  - No dashboard screen sets a stock quantity.
  - The low-stock and out-of-stock receiver is never connected (`inventory/signals.py:9-14`), so the notifications that wait on it never fire.
- **cms:**
  - Blocks and Forms have no create screen.
  - Linda's `email.templates` tool always reports `is_customised` as false (`cms/agent_tools.py:315`).
  - Linda's `cms.pages` tool always reports `published_at` as empty (`cms/agent_tools.py:288-290`).
- **media:** the library has no paging, and a large library silently drops older files (`media/views.py:256-258`, `media/templates/media/library.html:151`).
- **gdpr:** the `DataRequest` audit trail of export and deletion requests has no screen.
- **agent_mcp:** the API-tokens screen names the assistant "Janus" to merchants (`agent_mcp/dashboard.py:159-201`).
- **agent_core:** the Proposals tab is shown to superusers only (`admin_dashboard/navigation.py:154-163`), but its view admits any staff member (`core/assistant/views_proposals.py:20`).
- **morpheus_brain:** nothing calls `generate_daily_reports` (`morpheus_brain/services.py:122-131`), so the Daily Reports tab never gets an entry.

## Settings that change nothing

- **admin_dashboard:** `theme_mode`, `sidebar_collapsed` (`admin_dashboard/app.py:64-71`).
- **agent_core:** `merchant_ops_enabled` (`agent_core/app.py:341`).
- **ai_assistant:** `enable_synthetic_testing` (`ai_assistant/app.py:570-579`). Also, `MerchantInsight.ai_executed` is never set (`ai_assistant/models.py:422`).
- **ai_stylist:** `persona_name`, `welcome_message`, `require_consent`.
- **brand_kit:** `active_token_set` (`brand_kit/app.py:63-67`). The active set comes from `is_active` instead.
- **discovery_quiz:** `require_consent`.
- **flipbook:** `max_preview_pages = 0` is documented as "full book" but falls back to 20 pages (`flipbook/views.py:66,103`).
- **journal:** `enabled`.
- **media_3d:** both fields. The templates read a `settings` context nothing supplies.
- **motion:** `intensity`, `reduced_motion_default`.
- **one_click:** `enabled`.
- **pwa:** `enabled` (`pwa/app.py:78-83`).
- **rails:** `require_consent`.
- **referrals:** `enabled`.
- **returns_portal:** its description promises two fields the schema lacks.
- **storefront:** `enable_guest_checkout`, `products_per_page`, `show_out_of_stock`, `enable_live_search` and `enable_ai_chat` have no readers (`storefront/app.py:67-82`).
  - `core/tests/test_settings_keys_have_readers.py:34` exempts storefront through `DYNAMIC_READERS`, so the guard is blind to these.
  - Maintenance mode works but has no screen to switch it on.
- **tax:** `prices_include_tax` (`tax/models.py:109-112`).

## Apps that do nothing today

These apps have models but no working path:
- discovery_quiz, drops, journal (its slot is rendered by no theme);
- lookbook (no authoring screen);
- one_click, rails, save_for_later, ugc_reviews, media_3d, ai_stylist, referrals, rich_post_purchase, smart_shipping;
- environments, experiments, functions (none of them can be created).

Related:
- **experiments:** the cookie middleware isn't installed (`experiments/middleware.py:13`), so signed-out visitors never get a stable id.
- **environments:** its GraphQL scope `read:environments` isn't in `AVAILABLE_SCOPES` (`environments/graphql/queries.py:58,83`).
- **loyalty_points:**
  - The tier and RFM tasks are never scheduled (`loyalty_points/tasks.py:11-17`).
  - Its referral subsystem has no entry point, and its `ORDER_PLACED` hook is registered without the `plugin=` tag, so it keeps firing after the app is switched off (`loyalty_points/apps.py:17-34`).

## Descriptions and comments that claim more than the code does

- **ai_content:** bulk rewrite is said to be "callable from the Products list"; nothing calls it there (`ai_content/services_bulk_catalog.py:3`).
- **advanced_ecommerce:** the comment at `app.py:105-110` describes pages that don't exist, and `low_stock_view` is dead code.
- **audiobooks:** the product-form card says generation "is coming", while its Generate button already works (`audiobooks/templates/audiobooks/blocks/product_form_card.html:9`).
- **bookstore_3d, catalog:** stale comments (the slot name, the settings path).
- **brand_kit:** the "AI brand kit" generator doesn't exist (`brand_kit/app.py:12-14`).
- **cloudflare:** Turnstile is said to protect "contact, signup"; only the affiliate form uses it (`cloudflare/app.py:130`).
- **draft_orders:** the `sent`, `accepted` and `expired` states are never set, and nothing shares a draft with the customer or takes payment for it.
- **dsers:** unmapped products are flagged per product, not per variant.
- **flipbook:** the module docstring describes the old full-PDF reader.
- **importers:** advertises Magento and BigCommerce (no code exists) and a CSV of customers and orders (CSV covers products only) (`importers/app.py:12-15,35`).
- **lookbook:** promises dashboard authoring, "AI auto-look" and adding a whole look to the cart; none exists (`lookbook/app.py:4-10`).
- **marketing:** `marketing.Redirect` is a dead model; seo owns the live one.
- **microsoft_commerce:** the comments say reporting is "not built", but it works (`microsoft_commerce/app.py:8-12`, `agent_tools.py:28`).
- **observability:** says it holds "the error log"; it holds only the audit log, and `ErrorEvent` comments are stale.
- **openai_shopping:** the channels overview's "Connected" column reflects push setup, not whether the feed works (`openai_shopping/app.py:70-79`).
- **personalisation:** "Co-purchase recommendations on PDPs" are retired (`personalisation/app.py:18`).
- **post_checkout_upsell:** a one-tap "add to my order" doesn't exist (`post_checkout_upsell/app.py:13-14`), and the montenegro theme doesn't render its slot.
- **product_gallery:** the docstring names templates no theme uses.
- **rbac:** a stale comment contradicts `category='team'` (`rbac/app.py:84-89`).
- **returns_portal:**
  - `ReturnResolution` and `ReturnFeedback` are never used.
  - The CTA's `?action=return` is never read.
  - Its `requires` lists more apps than it uses.
- **rich_post_purchase:** the docstring reads like a built multichannel chain.
- **staff_mfa:** the "break-glass reset" is a server command, not a screen.
- **tax:** says it offers a "Stripe Tax adapter"; none exists (`tax/app.py:16-19`).
- **workflows:** said to be "visual no-code"; conditions and actions are raw JSON (`workflows/app.py:17`).
- **zendrop:** the connection test is cached for an hour across token changes, and a template names the wrong settings category.
- **core:** the `ExchangeRate` docstring points at `environments`, which has nothing to do with exchange rates (`core/models.py:298`).
- **live_commerce** (lower confidence): its pages check `cms.*` capabilities although they file under Marketing.

## Linda can't reach these merchant actions (owner rule: every capability ships its agent tool)

- openai_shopping (no tools at all)
- book_product (taxonomy and AI copy)
- bookvault (connect, resend, link)
- digital_products, gdpr (no screens either)
