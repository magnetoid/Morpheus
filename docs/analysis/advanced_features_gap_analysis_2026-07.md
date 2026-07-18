# Morpheus — Advanced E-Commerce Features Gap Analysis

> **Date:** 2026-07-18
> **Scope:** 15 advanced feature areas evaluated against current industry best practice (Shopify Plus / Adobe Commerce / BigCommerce / commercetools / Sharetribe / Klaviyo-class tooling), with every "current state" claim verified against source (`file:line` evidence).
> **Companion reports:** [enterprise_benchmark_gap_report_2026.md](enterprise_benchmark_gap_report_2026.md) (enterprise tier gaps), [core_codebase_audit_2026-07.md](core_codebase_audit_2026-07.md) (kernel quality), [platform_analysis_and_feature_proposals_2026.md](platform_analysis_and_feature_proposals_2026.md) (analytics/feature proposals).

---

## Executive Summary

Morpheus's advanced-feature portfolio is **wide but uneven in depth and wiring**. The honest pattern across this audit:

- **Genuinely strong:** AI personalization substrate, headless GraphQL, social channel integrations (feeds + pixels + server-side CAPI), subscription billing with dunning, loyalty with tiers + referrals, self-service RMA, multi-warehouse inventory core.
- **Shipped-but-dead (the most damaging class):** dynamic pricing computes multipliers that never reach a price; the AR viewer has a data model but no launcher; `returns_portal` exchange models have no consumers; `rich_post_purchase` collects SMS/WhatsApp preferences with no senders; PWA push stores subscriptions with no sender; fraud scores are computed but invisible to staff. **Six features present UI/settings surfaces that do nothing** — this erodes merchant trust faster than missing features.
- **Genuinely missing:** real-time supply chain tracking, localized payment methods for emerging markets, social checkout / inbound order sync, channel-scoped inventory, POS/BOPIS, marketplace payout automation, ML fraud scoring.

### Maturity scorecard (15 areas)

| # | Area | Status | Maturity |
|---|---|---|---|
| 1 | AI-driven personalization | SHIPPED | ★★★★☆ |
| 2 | Omnichannel inventory sync | PARTIAL | ★★☆☆☆ |
| 3 | Headless commerce | SHIPPED | ★★★★☆ |
| 4 | Multi-vendor marketplace | PARTIAL | ★★★☆☆ |
| 5 | Subscription billing + dunning | SHIPPED | ★★★★☆ |
| 6 | AR product preview | PARTIAL (dead-wired) | ★☆☆☆☆ |
| 7 | Real-time supply chain tracking | MISSING | ☆☆☆☆☆ |
| 8 | Dynamic pricing optimization | PARTIAL (inert) | ★☆☆☆☆ |
| 9 | B2B quotes & bulk ordering | PARTIAL | ★★★☆☆ |
| 10 | ML fraud detection | PARTIAL (rules only, invisible) | ★★☆☆☆ |
| 11 | Social commerce | SHIPPED | ★★★★☆ |
| 12 | PWA | SHIPPED (push partial) | ★★★☆☆ |
| 13 | Localized payment methods | PARTIAL | ★★☆☆☆ |
| 14 | Post-purchase CX (returns, loyalty) | PARTIAL | ★★★★☆ |
| 15 | Live commerce / creator economy | SHIPPED (MVP) | ★★★☆☆ |

### Gap totals by priority

| Priority | Count | Definition used |
|---|---|---|
| **Critical** | 6 | Shipped-but-dead surfaces (merchant-facing features that silently do nothing) or direct conversion blockers |
| **High** | 9 | Capabilities competitors ship that merchants will ask for in the first sales cycle |
| **Medium** | 10 | Depth/parity items that complete already-strong areas |
| **Low** | 8 | Strategic/roadmap items |

---

## Area 1 — AI-Driven Personalization Engine

**Status: SHIPPED — strongest area relative to market.**

**Evidence:** `personalisation` (embedding-similarity homepage reordering), `rails` (5 personalized feed rails), `dynamics` (multi-armed bandit merchandising), `discovery_quiz` (zero-party data capture), `ai_assistant` (brand voice, embeddings, pulse insights). RFM segmentation in [customers/rfm.py](file:///Users/magnetoid/coding/morph/plugins/installed/customers/rfm.py) with nightly recompute and `CUSTOMER_SEGMENT_CHANGED` hook.

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| Personalization surfaces dead-wired on PDP | **High** | `pdp_below_gallery` slot is not rendered by the dot_books theme — ugc_reviews gallery, media_3d blocks never display ([dead-wiring-2026-07.md](file:///Users/magnetoid/coding/morph/docs/plans/dead-wiring-2026-07.md)) |
| No cross-surface personalization memory | Medium | Per-surface models don't share a customer embedding profile; quiz answers don't inform rails |
| No merchandising guardrails UI | Medium | Bandit has no staff-facing "pin/exclude product" controls surfaced |
| No personalization performance reporting | Medium | No dashboard showing lift per personalized surface vs control |

**Implementation requirements (top gap):** render `pdp_below_gallery` in the theme (1 template line + block QA); unify customer embedding profile in `ai_assistant` and consume from `rails`/`dynamics` via a shared service (3–5 d).

---

## Area 2 — Omnichannel Inventory Synchronization

**Status: PARTIAL — strong single-pool core, zero omnichannel surface.**

**Evidence:** `Warehouse`, `StockLevel` (variant×warehouse, reserved quantities), atomic reserve/commit/release ([services.py](file:///Users/magnetoid/coding/morph/plugins/installed/inventory/services.py)), 3-strategy allocator, Redis fast-path + drift reconciliation, demand forecasting, `StockoutAlert`. But: `ProductChannelListing` ([core/models.py:140-175](file:///Users/magnetoid/coding/morph/core/models.py#L140-L175)) holds price + publish flags **only — no stock fields**; `StockLevel` has no channel FK.

**Gaps:**

| Gap | Priority | Detail | Best-practice benchmark |
|---|---|---|---|
| No channel-scoped inventory | **High** | All channels draw one global pool — no per-channel allocation, safety stock, or availability promise | Shopify multi-location, commercetools inventory channels |
| No POS integration | Medium | `Order.source='pos'` exists as a free-text vestige; no POS endpoints, sessions, or sync | Shopify POS, Square |
| No BOPIS / click-and-collect | Medium | No pickup-location model, no pickup fulfillment flow (0 code hits) | Standard in all enterprise tiers 2025+ |
| No supplier/vendor inventory feeds | Medium | No EDI/feed ingestion; marketplace vendors can't expose stock | EDI 846, SFTP feeds |
| Warehouse transfer workflow missing | **High** | `StockMovement.transfer` type exists; no create/execute UI or service | Basic WMS table stakes |

**Implementation requirements (channel-scoped inventory):** add nullable `channel` FK to `StockLevel` (null = shared pool); allocator resolves channel-pool first then shared; reservation ledger keys on (variant, warehouse, channel); migration + backfill; channel availability in `ProductChannelListing` computed from scoped levels. Est. 2–3 wks.

---

## Area 3 — Headless Commerce Architecture

**Status: SHIPPED — substantial, with three real gaps.**

**Evidence:** Strawberry GraphQL at `/api/graphql/` + agent-scoped `/api/graphql/agent/` ([api/urls.py:30-31](file:///Users/magnetoid/coding/morph/api/urls.py)); full catalog→cart→checkout→orders coverage via `register_graphql_extension`; `APIKey` model with scopes + channel FK ([core/models.py:187-228](file:///Users/magnetoid/coding/morph/core/models.py#L187-L228)); `MORPHEUS_THEME=none` API-only mode; REST v1 viewsets.

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| No customer account surface | **High** | `customers/graphql/queries.py` and `mutations.py` are comment-only stubs — no `me`, addresses, order history; a headless account area is not buildable |
| Session-cookie-bound carts | Medium | Pure token clients can't own a cart ([orders/graphql/queries.py:51-94](file:///Users/magnetoid/coding/morph/plugins/installed/orders/graphql/queries.py#L51-L94)) |
| HEADLESS.md schema drift | Low | Documents `products { edges { node } }` / `checkoutComplete`; implemented is list-based `products` / `completeOrder` |

**Implementation requirements (account surface):** `me` query (profile, addresses, orders paginated), `updateAddress`/`createAddress` mutations, token-scoped cart via `cartId` ownership check. Est. 1 wk.

---

## Area 4 — Multi-Vendor Marketplace Management

**Status: PARTIAL — real core, missing the automation layer.**

**Evidence:** `VendorApplication` onboarding + staff review ([dashboard.py:109-179](file:///Users/magnetoid/coding/morph/plugins/installed/marketplace/dashboard.py#L109-L179)); vendor self-service dashboard with KPIs/products/orders/payout requests; `VendorOrder` split on `ORDER_PLACED` with commission math ([services.py:20-65](file:///Users/magnetoid/coding/morph/plugins/installed/marketplace/services.py#L20-L65)); `VendorPayoutAccount` accrual; admin GMV/commission reports + CSV export.

**Gaps:**

| Gap | Priority | Detail | Benchmark |
|---|---|---|---|
| Payout execution is manual | **High** | No `stripe.Transfer`/Connect/PayPal Payouts call exists; "Stripe Connect" is a dropdown label ([views.py:480](file:///Users/magnetoid/coding/morph/plugins/installed/marketplace/views.py#L480)) | Sharetribe/Stripe Connect auto-payouts |
| No product moderation queue | **High** | Vendors set `status='active'` directly ([views.py:219-247](file:///Users/magnetoid/coding/morph/plugins/installed/marketplace/views.py#L219-L247)) — no approval step | Marketplace trust & safety table stakes |
| Commission inconsistency | **High** | Metafield override shown as "effective commission" in admin is **not** what `split_order` charges (reads only `vendor.commission_rate`) | Correctness bug, not just a gap |
| Dead config | Medium | `auto_approve_applications` declared, never read | — |
| No vendor shipping tooling | Medium | Manual tracking text only; no labels/rates per vendor | Shippo multi-seller |
| No per-category commissions | Medium | Single rate per vendor | Amazon/Sharetribe category fees |
| No vendor staff/roles | Low | Single owner FK | Multi-user vendor orgs |
| No refund flowback | Medium | Vendor balances not debited on refunds | Accounting correctness |
| No 1099/DAC7 tax docs | Low | Compliance at scale | Stripe tax forms |

**Implementation requirements (payout automation):** Stripe Connect Express onboarding flow in vendor settings; `VendorPayout.execute()` → `stripe.Transfer` with idempotency key; webhook reconciliation on `transfer.paid/failed`; balance debit on `transfer.failed`. Est. 2 wks. **(Moderation):** `ProductSubmission` state machine (draft→pending→approved/rejected), staff queue + vendor notification hooks. Est. 1 wk.

---

## Area 5 — Subscription Billing Automation + Dunning

**Status: SHIPPED — near production-grade.**

**Evidence:** Stripe adapter (sync/start/cancel/pause/resume, [stripe_adapter.py](file:///Users/magnetoid/coding/morph/plugins/installed/subscriptions/billing/stripe_adapter.py)); webhook reconciliation (invoice.paid/failed, subscription.updated/deleted); dunning drip with configurable step schedule (hourly beat, consent-gated); pre-renewal reminders; MRR/churn/trial-funnel/plan-breakdown analytics + dashboard; member discount via `CART_CALCULATE_BREAKDOWN`.

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| No proration / plan changes | **High** | No upgrade/downgrade mid-cycle — the #1 subscription support request |
| No subscribe-at-checkout | Medium | Spec'd as "later slice"; subscription products can't be bought in the normal cart flow |
| No usage-based/metered billing | Medium | No metering model or Stripe meter events |
| `subscriptions_plus` not wired to Stripe | Medium | Replenish/curated flavors exist but billing adapter integration deferred |
| No self-service payment-update portal | Low | Membership page exists; card-update flow is a link, not a portal |
| No revenue recognition (ASC 606) | Low | Enterprise finance requirement |

**Implementation requirements (proration):** `change_plan(subscription, new_plan, prorate=True)` via Stripe `proration_behavior='create_prorations'`; preview endpoint; mid-cycle invoice reconciliation test. Est. 1 wk.

---

## Area 6 — AR Product Preview

**Status: PARTIAL trending MISSING — the data model is right and everything after it is dead.**

**Evidence:** `Asset3D` with `glb_url` (Android Scene Viewer) + `usdz_url` (iOS Quick Look) + poster ([media_3d/models.py:13-34](file:///Users/magnetoid/coding/morph/plugins/installed/media_3d/models.py#L13-L34)) — the correct AR asset model. But: the viewer block renders only a `<button>` with **no JS handler anywhere** (zero hits for `model-viewer`/WebXR/Quick Look); the block never renders (no `asset` in PDP context + `pdp_below_gallery` slot unrendered); no upload/manage UI; the plugin docstring promises a GraphQL extension that doesn't exist. Separately, `bookstore_3d` ships a working three.js walkthrough (not AR).

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| AR launcher dead end-to-end | **Critical** | Model exists, nothing renders or launches — merchants see settings that do nothing |
| No asset management UI | **High** | `Asset3D` rows creatable only via shell/fixtures |
| No `<model-viewer>` / Quick Look integration | **High** | The standard web-AR path (model-viewer covers Scene Viewer + Quick Look) is absent |
| Promised GraphQL extension missing | Medium | Docstring contract unfulfilled |

**Implementation requirements:** dashboard upload page (Asset3D CRUD + glb/usdz validation + size budget); `<model-viewer>` web component in PDP block with `ar ar-modes="webxr scene-viewer quick-look"`; inject `asset` into PDP context via the block's context contract; render the slot in theme; GraphQL `product.asset3d` field. Est. 1–1.5 wks. **Conversion impact:** Shopify reports 94% higher conversion on products with 3D/AR content — highest ROI per effort in this report.

---

## Area 7 — Real-Time Supply Chain Tracking

**Status: MISSING.**

**Evidence:** only manual merchant-entered tracking (`Order.tracking_number`, `Fulfillment` status FSM, [orders/models.py:179,312-335](file:///Users/magnetoid/coding/morph/plugins/installed/orders/models.py#L179)); post_purchase "delivered" emails are **timers, not carrier events** ([tasks.py:74-91](file:///Users/magnetoid/coding/morph/plugins/installed/post_purchase/tasks.py#L74-L91)); `smart_shipping` advertises EasyPost/Shippo but ships **no adapter code** (carbon table + model only). Zero carrier webhooks, zero PO/ASN/lead-time models.

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| No carrier tracking integration | **High** | No Shippo/EasyPost/AfterShip tracker webhooks; delivery status never updates automatically |
| No customer delivery-status page | **High** | Account order detail shows manual status only; "where is my order" (WISMO) is the #1 support driver — 30–50% of tickets industry-wide |
| No inbound supply chain (PO/ASN/lead times) | Medium | No purchase orders, no advanced shipping notices, no supplier lead-time tracking feeding the demand forecast |
| smart_shipping is a hollow shell | **Critical** | Advertised carrier integrations don't exist; its block targets an unrendered slot |

**Implementation requirements (tracking):** register EasyPost tracker per fulfillment (webhook → `Fulfillment.status` transitions); public `/track/<order>/` page with timeline; trigger real delivered events into `post_purchase` (replacing timers). Est. 1.5–2 wks. **(smart_shipping):** either implement the advertised EasyPost/Shippo rate adapters or correct the plugin description — decide explicitly.

---

## Area 8 — Dynamic Pricing Optimization

**Status: PARTIAL and currently INERT — computes prices that never reach a customer.**

**Evidence:** `DynamicPricingService` ([pricing.py](file:///Users/magnetoid/coding/morph/plugins/installed/ai_assistant/services/pricing.py)) — inventory-only rules (>100 → ×0.95, <10 → ×1.15), hourly Celery evaluation, `DynamicPriceRule` model. **Critical:** the `PRODUCT_CALCULATE_PRICE` filter it subscribes to is **never fired anywhere** — definition in [core/hooks.py:482](file:///Users/magnetoid/coding/morph/core/hooks.py#L482), zero fire sites. Also a silently dead VIP branch (`customer.is_vip` doesn't exist on the user model).

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| Price filter never fired | **Critical** | Feature is end-to-end inert even when enabled. The dead-wiring doc defers this deliberately ("do NOT half-wire the money path") — so the fix is a designed money-path project, not a one-liner |
| Rules engine only, no ML | Medium | Single signal (inventory); no demand elasticity, competitor pricing, time-of-day, or per-segment pricing |
| Dead VIP branch | Low | References nonexistent `customer.is_vip` |
| No pricing guardrails | Medium | No floor/ceiling, no margin protection, no approval workflow for AI-suggested prices |

**Implementation requirements (wire the money path — designed project):** fire `PRODUCT_CALCULATE_PRICE` from a single authoritative price-resolution service consumed by PDP/cart/checkout; pricing audit log (rule, inputs, before/after); floor/ceiling guardrails; A/B measurement via `experiments`. Est. 2–3 wks including money-path tests. **Then** layer demand signals (sales velocity from `AnalyticsEvent`, elasticity from price-change history). Note: B2B price resolution (Area 9) should ride the same price-resolution service — build once.

---

## Area 9 — B2B: Quote Management & Bulk Ordering

**Status: PARTIAL — solid foundation, broken last mile.**

**Evidence:** `PriceList`/`PriceListItem`, `Quote`/`QuoteLine` lifecycle, `NetTermsAgreement`, bulk CSV ordering with account pricing ([services_bulk_order.py](file:///Users/magnetoid/coding/morph/plugins/installed/b2b/services_bulk_order.py)), CRM `Account` model, agent tools.

**Gaps** (full B2B enterprise detail in the companion enterprise report; condensed here):

| Gap | Priority | Detail |
|---|---|---|
| Quote→order conversion missing | **High** | `Quote.converted_order` FK exists; no conversion service — accepted quotes die |
| B2B pricing invisible in storefront/checkout | **High** | `resolve_price_for_account()` works only in the CSV path — B2B buyers browse at retail prices |
| No tiered/volume pricing | **High** | Flat per-product overrides only; no quantity breaks |
| No purchase orders / invoice-me checkout | **High** | Net-terms buyers can't check out without a card |
| No RFQ from storefront | Medium | Quotes are staff-initiated only |
| No customer-group pricing, MOQ, requisition lists, shared catalogs | Medium | Standard wholesale depth (Adobe/BigCommerce ship these) |

**Implementation requirements (quote→order + storefront pricing):** `convert_quote_to_order(quote)` creating a draft order at quoted prices with expiry validation; fire account-price resolution through the same unified price-resolution service as Area 8 (PDP, cart, checkout). Est. 2 wks combined with the price-service work — **do them together**.

---

## Area 10 — Advanced Fraud Detection with ML

**Status: PARTIAL — deterministic rules shipped; everything intelligent and every staff surface missing.**

**Evidence:** 6 rules (IP velocity +30, email velocity +20, address mismatch +15, BIN denylist +25, refund-fraud history +30, first-order-high-value +10) with additive scoring → ok/watch/review/reject buckets ([services.py:62-96](file:///Users/magnetoid/coding/morph/plugins/installed/fraud_rules/services.py#L62-L96)); results stamped on `order.metadata`; fail-open on error.

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| No staff review queue | **Critical** | Score ≥60 logs a warning — nothing else. No dashboard page, no notification, no review model (the plugin has no `models.py`). Flagged orders are operationally invisible |
| BIN rule is dead | **High** | Denylist ships empty and **nothing in the codebase writes `payment_bin`** to order metadata |
| `auto_reject_at_score` config unread | **High** | Declared "Phase 2", nothing reads it — no auto-action exists at any score |
| No ML scoring | Medium | Pure heuristics; no model, no learning from outcomes (chargebacks/refunds as labels) |
| No device fingerprinting | Medium | No fingerprint signals at all |
| No third-party integration | Medium | No Stripe Radar signals ingestion, Sift, or MaxMind |
| Fail-open on error | Low | Scoring failure returns 0 (deliberate, but should emit a notification) |

**Implementation requirements (review queue — do first):** `FraudReview` model (order, score, flags, state pending/approved/rejected, reviewer, decided_at); `notifications_center` alert on review/reject; dashboard queue with order context + approve/cancel-order actions; wire `auto_reject_at_score` to hold fulfillment (not cancel payment) above threshold. Est. 1 wk. **(ML later):** label orders with chargeback/refund outcomes, train gradient-boosted scorer offline, blend score = 0.5×rules + 0.5×model behind the existing `FraudResult` contract. Est. 3–4 wks + data maturity.

---

## Area 11 — Social Commerce Integrations

**Status: SHIPPED — one of the strongest areas.**

**Evidence:** 8 channel plugins; 6 ship catalog feed + pixel/tag + server-side CAPI + ads management (`meta_commerce`, `google_shopping`, `tiktok_commerce`, `pinterest_commerce`, `snapchat_commerce`, `reddit_ads` + `microsoft_commerce` without CAPI, `amazon_ads` ads-only by design); `live_commerce` MVP (YouTube/HLS events with pinned products); `ugc_reviews` creator tier with stipend credits; `affiliates`.

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| No inbound order sync | **High** | Zero order-pull from any channel — marketplace orders (Amazon SP-API, TikTok Shop) don't flow into Morpheus; merchants manage two order books |
| No social checkout | Medium | No Meta Shops/Instagram Checkout/TikTok Shop in-app checkout participation |
| UGC PDP gallery dead-wired | **High** | ugc_reviews blocks target the unrendered `pdp_below_gallery` slot (same fix as Area 1/6) |
| Microsoft CAPI missing | Medium | UET tag only; no server-side conversions |
| No shoppable UGC galleries | Medium | Photo/video reviews can't be curated into shoppable storefront galleries |

**Implementation requirements (order sync — start with Amazon SP-API since the ads plugin already has auth groundwork):** `ChannelOrder` model (external_id, channel, mapped `Order`); scheduled pull with cursor persistence; SKU→variant mapping; fulfillment status pushback. Est. 3–4 wks for Amazon + a generic `ChannelOrderAdapter` the other channels can implement.

---

## Area 12 — Progressive Web App (PWA)

**Status: SHIPPED (install + offline), PARTIAL (push).**

**Evidence:** full Web App Manifest with maskable icons ([pwa/views.py:51-97](file:///Users/magnetoid/coding/morph/plugins/installed/pwa/views.py#L51-L97)); service worker — network-first navigations + offline fallback, cache-first static, auth/cart/checkout exclusions; offline page; registration block on a rendered slot; 4 contract tests.

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| Push has no sender | **Critical** | `PushSubscription` registry + endpoints shipped, but zero send code (no pywebpush, no VAPID consumer) — merchants can collect subscribers and never message them |
| Duplicate shadowed service worker | **High** | Older `storefront/sw.py` mounts the same `/sw.js`; pwa shadows it by registration order — two settings toggles for one surface |
| No install prompt UX | Medium | No `beforeinstallprompt` handling or custom install banner |
| No push campaign integration | Medium | Registry has `topics` but nothing (post_purchase, promotions, back-in-stock) sends pushes |

**Implementation requirements (push sender):** add `pywebpush` dependency; VAPID keypair in settings (`format: password` for the private key); `send_push(subscription, payload)` service with 410-gone cleanup; wire first sender to back-in-stock (highest-intent trigger). Est. 3–4 d. **(Dedup):** retire `storefront/sw.py` behind a migration note. 0.5 d.

---

## Area 13 — Localized Payment Methods (Emerging Markets)

**Status: PARTIAL — three rails, zero explicit local methods.**

**Evidence:** Stripe (PaymentIntent + `automatic_payment_methods` + saved-card vault), PayPal (redirect flow), manual/COD + test gateway ([gateway.py:57-93](file:///Users/magnetoid/coding/morph/plugins/installed/payments/gateway.py#L57-L93)). Apple Pay domain verification shipped. `automatic_payment_methods` means Klarna/Link/etc. work **only if the merchant enabled them in the Stripe dashboard** — nothing in Morpheus surfaces or validates this.

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| No emerging-market methods | **Critical** (for emerging-market merchants) | Zero explicit Pix (Brazil), UPI (India), M-Pesa (Africa), Boleto, OXXO, GrabPay, Alipay/WeChat Pay — these aren't optional in their markets: Pix is ~40% of Brazilian e-commerce; cards are a minority rail in India/SEA |
| No local acquirer gateways | **High** | No Mollie (iDEAL/Bancontact), Adyen, Razorpay, Mercado Pago, Paystack, Flutterwave — the plugin gateway contract exists (`GATEWAY_TYPES` includes `plugin`) but no one has used it |
| No method-specific flows | **High** | Pix/Boleto/OXXO need async voucher/QR confirmation UIs; SEPA needs mandate handling — none exist |
| No method eligibility by market | Medium | `markets` knows the customer's country; checkout doesn't filter offered methods by it |

**Implementation requirements (phased by market ROI):** **Phase 1 (Stripe-native, no new acquirer):** Pix, Boleto, iDEAL, SEPA, Klarna, Alipay via Stripe Payment Element + `payment_method_types` per `markets` country + async-confirmation order state (`awaiting_payment_action`). Est. 2–3 wks. **Phase 2 (acquirer plugins):** Razorpay (UPI/cards/netbanking) and/or Mercado Pago (Pix/Boleto/OXXO + local cards) as new gateway plugins implementing the existing contract — validates the `plugin` gateway type end-to-end. Est. 2 wks each. **Phase 3:** M-Pesa via Paystack/Flutterwave when an African merchant demands it.

---

## Area 14 — Post-Purchase CX: Returns Automation & Loyalty

**Status: PARTIAL — loyalty is excellent, returns are good, exchanges/multichannel are stubs.**

**Evidence:** journey emails + NPS with signed-token forms and dashboard ([post_purchase](file:///Users/magnetoid/coding/morph/plugins/installed/post_purchase/)); self-service RMA with 6-state machine, store-credit refunds, over-refund guard, restock hook ([orders/refunds.py:192-320](file:///Users/magnetoid/coding/morph/plugins/installed/orders/refunds.py#L192-L320)); full loyalty — ledger, earn/burn, cart discount, tiers (Bronze/Silver/Gold trailing-12m), referrals with rewards, RFM.

**Gaps:**

| Gap | Priority | Detail |
|---|---|---|
| `returns_portal` is a stub | **Critical** | `ReturnResolution` (refund/exchange/store_credit) + `ReturnFeedback` models shipped with **zero consumers** — no views, urls, or services; exchanges never execute |
| `rich_post_purchase` has no senders | **Critical** | Collects SMS/WhatsApp/push opt-ins (AES-GCM stored) with settings UI — nothing can send; "Twilio" appears only in a docstring |
| No return label generation | **High** | No carrier integration for prepaid labels — the biggest returns-automation gap vs Loop/ReturnBear-class tools |
| No exchange execution | **High** | No replacement-order creation path at all |
| No reorder / buy-again flow | Medium | Zero hits for reorder/buy-again — cheapest repeat-purchase UX win |
| Duplicate referral systems | Medium | `loyalty_points` referrals and `referrals` plugin are parallel implementations — consolidate to one owner |
| Loyalty has no expiry/breakage rules | Low | Points never expire; no breakage analytics |

**Implementation requirements (exchanges):** `ExchangeService.create(exchange_request)` → replacement draft order (price delta handling) linked to the return; auto-restock on receive. Est. 1 wk. **(Multichannel senders):** Twilio SMS/WhatsApp sender + PWA push sender (Area 12) behind `ChannelPreference`; migrate post_purchase dispatch to channel-aware sender registry. Est. 1–1.5 wks. **(Labels):** EasyPost return labels on RMA approval (same integration as Area 7 tracking). Est. 3–4 d — do with Area 7.

---

## Area 15 — Live Commerce / Creator Economy

**Status: SHIPPED (MVP) — ahead of most competitors, with known limits.**

**Evidence:** `live_commerce` — `LiveEvent` + pinned products, YouTube/HLS embed, replay, storefront + dashboard routes. `ugc_reviews` creator tier + stipends. `affiliates` with CSV exports.

**Gaps:** WebRTC/native streaming + live chat (documented out-of-scope) — Medium; real-time event analytics overlay — Medium (realtime pipeline exists to piggyback); shoppable VOD with timestamped product cards — Medium (blocked by the dead media_3d wiring).

---

## Consolidated Priority Matrix

### Critical — shipped-but-dead or direct conversion blockers (fix first)

| ID | Gap | Area | Effort | Primary impact |
|---|---|---|---|---|
| AF-C1 | Dynamic pricing inert — fire `PRODUCT_CALCULATE_PRICE` via a unified price-resolution service | 8 (+9) | 2–3 wks | Revenue optimization; also unblocks B2B storefront pricing |
| AF-C2 | AR viewer dead end-to-end — launcher JS, PDP context, slot render, upload UI | 6 | 1–1.5 wks | Conversion (3D/AR ≈ +94% on enabled products, Shopify data) |
| AF-C3 | Fraud review queue missing — flagged orders invisible to staff | 10 | 1 wk | Loss prevention; ops efficiency |
| AF-C4 | `returns_portal` stub — exchanges/resolutions never execute | 14 | 1 wk | Retention (exchanges retain ~30% of return revenue vs refunds) |
| AF-C5 | `rich_post_purchase` no senders + PWA push no sender | 14+12 | 1–1.5 wks | Retention channel ROI (push/SMS open rates ≫ email) |
| AF-C6 | Localized payment methods absent (Pix/UPI/iDEAL/SEPA/Boleto/Klarna via Stripe first) | 13 | 2–3 wks | Conversion in non-card markets (Pix ≈40% of Brazilian e-comm) |
| AF-C7 | `smart_shipping` hollow — implement or de-advertise | 7 | 0.5–2 wks | Merchant trust |

### High — first-sales-cycle expectations

| ID | Gap | Area | Effort | Impact |
|---|---|---|---|---|
| AF-H1 | Carrier tracking webhooks + customer tracking page (EasyPost) | 7 | 1.5–2 wks | WISMO tickets −30–50%; enables real "delivered" journeys |
| AF-H2 | Marketplace payout automation (Stripe Connect) | 4 | 2 wks | Marketplace ops scalability |
| AF-H3 | Marketplace product moderation queue | 4 | 1 wk | Marketplace trust & safety |
| AF-H4 | Marketplace commission inconsistency fix (split reads the override) | 4 | 1–2 d | Revenue correctness |
| AF-H5 | Channel-scoped inventory | 2 | 2–3 wks | Omnichannel oversell prevention |
| AF-H6 | Warehouse transfer workflow (UI + service over existing movement type) | 2 | 1 wk | Ops efficiency |
| AF-H7 | Quote→order conversion + B2B prices in storefront/checkout (rides AF-C1 price service) | 9 | 2 wks | B2B conversion |
| AF-H8 | Tiered/volume pricing + MOQ | 9 | 1–2 wks | Wholesale AOV |
| AF-H9 | Headless customer account surface (`me`, addresses, orders) | 3 | 1 wk | Headless completeness |
| AF-H10 | Inbound order sync framework (Amazon SP-API first) | 11 | 3–4 wks | Marketplace channel ops |
| AF-H11 | Return label generation (with AF-H1 integration) | 14 | 3–4 d | Returns automation |
| AF-H12 | Subscription proration / plan changes | 5 | 1 wk | Subscription LTV, support load |
| AF-H13 | Dead PDP slots — render `pdp_below_gallery` (unblocks Areas 1/6/11) | 1/6/11 | 0.5 d | Multiplies value of three shipped plugins |
| AF-H14 | Fraud: write `payment_bin`, wire `auto_reject_at_score` to hold fulfillment | 10 | 1–2 d | Loss prevention |

### Medium — parity and depth

| ID | Gap | Area |
|---|---|---|
| AF-M1 | ML fraud scoring blended into `FraudResult` (labels from chargebacks/refunds) | 10 |
| AF-M2 | POS integration foundation (sessions, barcode checkout, sync) | 2 |
| AF-M3 | BOPIS / click-and-collect | 2 |
| AF-M4 | Supplier inventory feeds + inbound PO/ASN (feeds demand forecast) | 7 |
| AF-M5 | Usage-based/metered subscription billing | 5 |
| AF-M6 | Subscribe-at-checkout flow | 5 |
| AF-M7 | Social checkout (TikTok Shop/Meta) | 11 |
| AF-M8 | PWA install prompt UX; retire duplicate storefront SW | 12 |
| AF-M9 | Reorder / buy-again flow | 14 |
| AF-M10 | Personalization lift reporting + merchandising guardrails UI | 1 |
| AF-M11 | RFQ from storefront; requisition lists; shared catalogs | 9 |
| AF-M12 | Consolidate duplicate referral systems; loyalty expiry rules | 14 |

### Low — strategic/roadmap

| ID | Gap | Area |
|---|---|---|
| AF-L1 | Native WebRTC live streaming + chat | 15 |
| AF-L2 | Shoppable VOD (blocked by media_3d wiring) | 15/6 |
| AF-L3 | Vendor staff roles; 1099/DAC7; per-category commissions; refund flowback | 4 |
| AF-L4 | Local acquirer gateways (Razorpay/Mercado Pago/Paystack) as plugin validations | 13 |
| AF-L5 | Device fingerprinting signals for fraud | 10 |
| AF-L6 | Revenue recognition (ASC 606) reporting | 5 |
| AF-L7 | Cross-surface unified customer embedding profile | 1 |
| AF-L8 | Microsoft CAPI | 11 |

---

## Phased Integration Roadmap

### Phase 1 — Resurrection Sprint (Weeks 1–4): kill the dead surfaces

**Theme:** six shipped features do nothing. Fix wiring before building anything new — cheapest trust recovery in the platform.

- AF-H13 render PDP slot (0.5 d — do day 1) → instantly unblocks UGC gallery, media_3d, AR surface
- AF-C2 AR launcher + upload UI (1.5 wks)
- AF-C3 fraud review queue (1 wk) + AF-H14 bin/auto-reject wiring
- AF-C4 exchange execution (1 wk)
- AF-C5 push/SMS senders (1.5 wks)
- AF-H4 commission fix (2 d) + AF-C7 smart_shipping decision (implement adapters or fix description)
- **Exit criteria:** zero merchant-facing settings that produce no behavior; fraud queue live with first reviewed order; first AR Quick Look launch on staging; first push notification delivered.

### Phase 2 — Revenue Paths (Weeks 5–10): money correctness + conversion

- AF-C1 unified price-resolution service firing `PRODUCT_CALCULATE_PRICE` (2–3 wks, money-path tests) — then immediately:
- AF-H7 quote→order + B2B storefront pricing riding the same service (2 wks)
- AF-H8 tiered pricing + MOQ (1–2 wks)
- AF-C6 localized payments Phase 1 via Stripe (2–3 wks)
- AF-H12 subscription proration (1 wk)
- **Exit criteria:** dynamic price multiplier visible on PDP/cart/checkout with audit log; B2B account sees its price everywhere; Pix/iDEAL/SEPA/Klarna completing in staging per-market.

### Phase 3 — Operations & Retention (Weeks 11–16): logistics + marketplace + channels

- AF-H1 carrier tracking + customer tracking page + real delivered events (2 wks)
- AF-H11 return labels (3–4 d, same integration)
- AF-H2 marketplace payout automation (2 wks) + AF-H3 moderation queue (1 wk)
- AF-H6 warehouse transfers (1 wk)
- AF-H9 headless account surface (1 wk)
- AF-M9 reorder flow (3–4 d)
- **Exit criteria:** WISMO-status page live with carrier events; first automated vendor payout on staging; vendors can't publish unmoderated products.

### Phase 4 — Scale & Intelligence (Weeks 17–26): the depth layer

- AF-H5 channel-scoped inventory (2–3 wks)
- AF-H10 inbound order sync framework + Amazon adapter (3–4 wks)
- AF-M1 ML fraud scoring blended into `FraudResult` (3–4 wks, needs outcome data maturing since Phase 1)
- AF-M4 supplier feeds/PO/ASN into demand forecast (2–3 wks)
- AF-M2/M3 POS/BOPIS foundation (per merchant demand)
- AF-L1/L2 live-commerce depth; AF-L4 acquirer gateways per market entry
- **Exit criteria:** per-channel availability promises; single order book across channels; fraud model outperforming rules-only baseline on precision@review.

---

## Impact Summary (mapped to business outcomes)

| Outcome | Highest-leverage items | Mechanism |
|---|---|---|
| **Conversion rate** | AF-C6 localized payments, AF-C2 AR, AF-H7 B2B pricing, AF-H8 tiered pricing | Right rail per market (Pix ≈40% of BR e-comm); 3D/AR ≈ +94% on enabled products; B2B buyers can't buy at retail prices |
| **Customer retention** | AF-C5 push/SMS senders, AF-H1 tracking, AF-C4 exchanges, AF-H12 proration, AF-M9 reorder | Owned re-engagement channels; −30–50% WISMO tickets; exchanges keep ~30% of return revenue; self-serve plan changes |
| **Operational efficiency** | AF-C3 fraud queue, AF-H2 payout automation, AF-H6 transfers, AF-H10 order sync, AF-C7 honest shipping | Staff stop hunting invisible flagged orders; manual payout/marketplace work eliminated; one order book |
| **Merchant trust (platform-level)** | Phase 1 in full | Six dead surfaces → zero. Every settings page does what it says |

**One architectural note that pays for Phase 2 twice:** the unified price-resolution service (AF-C1) is the single integration point for dynamic pricing (Area 8), B2B account pricing (Area 9), tiered pricing (AF-H8), and market pricing (existing `markets` plugin). Building it once prevents four parallel money paths — and the repo's own dead-wiring doc explicitly warns against half-wiring this path.

---

*Method note: every "shipped/partial/missing" verdict cites verified source locations gathered in two parallel repo sweeps (July 2026); competitor benchmarks draw on the repo's existing competitive research corpus. Industry figures (3D/AR conversion lift, Pix market share, WISMO ticket share, exchange retention) are directional industry benchmarks for prioritization, not platform-measured values.*
