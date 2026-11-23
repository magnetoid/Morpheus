# Morpheus as an e-commerce platform — gap analysis and completion plan (Nov 2026)

**Status:** approved by the owner on 2026-11-09. A1 (tax) v0.149.0, A2 (promotions) v0.150.0, A3 (inventory) v0.152.0, A4 (fulfilment and shipping rates) v0.154.0, A5 (payments, with the A4 choices as settings) v0.155.0, A7 (checkout fields) v0.168.0 and A8 (payment link) v0.171.0 are live on all five stores. F1 (AI marks on translations and images) v0.177.0 is live on all five stores (2026-11-18). F2 (claims and legal copy) v0.178.0 is live on all five stores (2026-11-18). P6 (manifest compatibility, third in the merged order) v0.179.0 is live on all five stores (2026-11-19). A10a (cancel and refund rules, fourth) v0.180.0 is live on all five stores (2026-11-20). F3 (the online withdrawal function, fifth) v0.181.0 is live on all five stores (2026-11-20). P8 (agent-coverage ratchet, sixth) v0.182.0 is live on all five stores (2026-11-20). P9 (app skills for Linda, seventh) v0.187.0 is live on all six stores (2026-11-22). C4 (customer returns and exchanges, eighth) v0.188.0 is live on all six stores (2026-11-23). C1 (post-purchase emails, ninth) is v0.189.0, in review. From A5 on, each commerce choice is a merchant setting whose default is the earlier behaviour (owner, 2026-11-12). Update the status column of the release tables as each release ships; this file is the plan of record (a plan in a chat does not survive `/clear`).

**Order of work:** from 2026-11-18 the remaining rows here and in [janus-alignment-and-app-platform-2026-11.md](janus-alignment-and-app-platform-2026-11.md) run in one merged order, set out in the next section. It replaces "platform first, then commerce" (owner, 2026-11-15).

## Order of work from 2026-11-18

**Owner's decision (2026-11-18).** The trends research of 2026-11-18 is accepted, and its order is the plan. Morpheus is a product any store runs, so every row ships inside Morpheus as an app or a setting, for any store. Nothing is built for one of the five stores or fixed by hand on one: they switch a feature on the way any other store would. The rule of 2026-11-12 still holds for each choice:
- a setting in the owning app's schema, with today's behaviour as the default;
- its reader and its Linda tool in the same change.

Where that default leaves a store outside a rule that may bind it, the setup checklist and the nightly health check say so. The platform never switches the feature on behind the merchant.

**What the research found.** The specifications and statutes were read. Every conversion or traffic number came from a vendor. The rules are a register drawn from law-firm commentary, not legal advice; dated rules are kept in [obligations-register.md](obligations-register.md).
- **Assistants send shoppers; the merchant takes the payment.**
  - ChatGPT Instant Checkout was reported withdrawn in March 2026.
  - Google admits merchants to UCP checkout from a US waitlist.
  - Shopify's Fall '26 edition makes WebMCP tools, a store-facts file and UCP checkout the default on its stores.
  - Morpheus's agent side (feeds, llms.txt, the UCP profile, ACP sessions, Web Bot Auth, WebMCP tools, the consent kernel) is in place. Its exposure is the selling side.
- **Three EU rules carry dates:**
  - the online withdrawal function (Consumer Rights Directive Art. 11a, from Directive 2023/2673), since 19 June 2026;
  - the ban on generic environmental claims (Directive 2024/825), since 27 September 2026;
  - machine-readable marks on AI-generated content (AI Act Art. 50), whose grace period for systems already on the market ends on 2 December 2026.
- **Card reach.** Stripe lists Croatia as a business location; it does not list Serbia or Montenegro. Monri, which absorbed WSPay, lists all three, on its own pages. Wallets, capture on shipment, the visitor's currency and agent checkout all assume a card rail.
- **Already in v0.176.0** (checked while planning, so not rows):
  - one-click unsubscribe headers (RFC 8058) on newsletter, cart-abandonment and core marketing mail;
  - an accessibility page among gdpr's legal pages;
  - a shipping rate's estimated days (a dashboard field, read by structured data). Checkout does not show them; that is F5.

**The order.** One release in flight. Each starts from a fresh worktree off `origin/main`, is versioned with `manage.py release`, and merges only on the owner's yes.

| # | Release | Row | Why here |
|---|---|---|---|
| 1 | AI marks on translations and images | F1 | the grace period ends on 2 December 2026 |
| 2 | Claims and legal copy check | F2 | in force since 27 September 2026 |
| 3 | Manifest compatibility and upgrades | P6 | the next platform row |
| 4 | Cancel and refund rules | A10a | a withdrawal or a return that ends in a wrong refund is worse than none |
| 5 | Online withdrawal function | F3 | in force since 19 June 2026; needs 4 |
| 6 | Agent-coverage ratchet | P8 | every later row ships its tools under it |
| 7 | App skills for Linda | P9 | live, v0.187.0 (2026-11-22) |
| 8 | Customer returns and exchanges | C4 | v0.188.0, live on all six (2026-11-23); its tools are P10's returns batch |
| 9 | Post-purchase emails | C1 | v0.189.0, in review |
| 10 | "Email customer" action and newsletter composer | C2 | |
| 11 | Regional card gateway app | F4 | card reach for stores Stripe does not serve |
| 12 | Delivery estimate at checkout | F5 | small; the data is already stored |
| 13 | Order editing and payment delta | A10b | after returns |
| 14 | Subscription cancel and pause by the customer | F6 | the same account surface |
| 15 | Store facts for agents | D3, widened | the first row of the agent door |
| 16 | API contract repair; webhook hardening | B1, B5 | UCP's minimums |
| 17 | Role grants and an enforce dry-run | E1, moved up | it bounds each staff member's Linda |
| 18 | Tool batches: consent, GDPR, then the rest | P10 | |
| 19 | Marketplace money | A11 | before any vendor payout |
| 20 | B2B, without VAT ID and reverse charge in the first cut | A9 | tax is not a priority (owner, 2026-11-11) |
| 21 | Checkout in the visitor's currency | markets release 2 | needs a card rail (11, or Stripe live) |
| 22 | UCP cart transfer | D2, narrowed | after 15 and 16 |
| 23 | Anonymous read-only storefront MCP | D1 | after 15 |
| then | A6's rest, B2–B4, C3, C5–C7, E2–E6, F7 | | as planned |

**Held or not done.**
- D4 (ACP on by default) is held until OpenAI's feed or ACP checkout opens to European sellers.
- Not done:
  - per-shopper personalised pricing;
  - a tax, OSS or duties engine (owner, 2026-11-11);
  - a fork or patch of Janus;
  - a hosted search engine at this catalogue size.
- Still parked: marketplace and TikTok Shop order sync, SMS, WhatsApp.

**Owner actions, not releases.**
- Run one live card payment on a store whose legal entity Stripe supports, and enter shipping rates on the selling stores. Both have been open since the October plan.
- Say which legal entity sells on each store. That decides which stores switch on F4 instead of Stripe.
- Croatia's base-price display and machine-readable price lists (reported for 17 November 2026; the sources conflict): confirm with counsel.
- Allow the read of live `AgentRun` rows that measures P4's tool search on real turns.

**Triggers that move a row.**
- Google admits self-hosted merchants to UCP checkout outside the US, or OpenAI's feed opens to EU sellers: widen D2 to native checkout and revisit D4.
- Each revision of the Web Bot Auth draft: re-test the verifier.
- The Digital Fairness Act proposal of 11 November 2026 (a termination button for digital subscriptions) and the UK subscription regime (January or spring 2027): both shape F6.

## Context

The owner's read is "partly unfinished, but heading the right way". This report tests that against the tree (v0.148.2, 98 apps, 5,762 tests, 343 releases since June) and against three reference points: **Medusa v2** (v2.22.6, 2026-11-09), **Saleor** (3.23, Apr 2026; 3.24 on main) and **Shopify's 2026 direction** (Winter '26 "Renaissance", Spring '26 "Everywhere", Fall '26 "Exponential"). Platform-as-infrastructure (SaaS vs self-hosted, Node vs Python) is deliberately ignored; the comparison is feature depth.

Method: three read-only code audits (engine depth, platform surfaces/API, completeness and debt) and three web research tracks (Medusa, Saleor, Shopify + 2026 trends and EU regulation). The strongest engine claims were re-verified by grep before they were written here (marked ✔). Owner decisions (2026-11-09): **rank by the general commerce engine** (what any serious merchant hits first; parity with Medusa/Saleor), and **finish the half-built apps rather than remove them**.

How the plan runs: one release in flight at a time, each its own version (`manage.py release`), each with its Linda tools, `help.md` lines and tests, merged only on an explicit yes (a merge deploys five stores).

## Verdict

The owner's feeling is accurate, and it has a shape:

- **Ahead of Medusa and Saleor:** the kernel (hooks bus with disable-gating, contributions, plugin/core boundary ratchets, safe deploys with pre-deploy backup + restore + automatic rollback, migration gate), the **merchant-side agent layer** (Janus with ~235 `@tool`s behind one gate chain, consent kernel, MCP admin edge, automations, AI-Act report, provenance marks), **compliance built in** (Omnibus price history, GPSR, Art. 50 marks, consent that server-side sends obey, WCAG audits, PCI 4.0.1 checkout CSP, Turnstile) and **the money invariants that exist** (fail-closed reservations, tender ordering, idempotent refunds, Stripe hardening, digital delivery). Neither Medusa nor Saleor ships any of the compliance items; both have read-only MCP (Medusa's Cloud-only).
- **Behind Medusa and Saleor — the second layer of the commerce engine.** Models exist with no consumer: tax category rates can never apply, coupon scope is never enforced, B2B price lists/net terms/quotes change nothing, four per-market price stores with one wired, warehouses without a screen, partial fulfilment without a form, no order editing, no capture, no exchanges, no customer returns screen. Medusa's Order module (edits/exchanges/claims, versioned timeline), Promotion module (campaigns + budgets, buy-X-get-Y), Pricing module (price lists per customer group), Inventory + Stock Location modules; Saleor's refund grant flow, warehouse→channel stock, promotions with predicates, Transactions API — all of that is working product there and half-wired here.
- **Below both on the headless contract:** no customer auth over GraphQL, cookie-bound carts, no pagination/facets, the STABLE doc names mutations and routes that do not exist, the schema is not CI-gated, no OpenAPI, no TS SDK.
- **On agentic commerce:** ahead of Medusa/Saleor on the merchant side, behind Shopify on the shopper side. Shopify (Spring/Fall '26) ships UCP default-on, Catalog/Cart/Checkout/Order MCP servers, WebMCP in every storefront, agent profiles with trust tiers and a merchant "knowledge base" for agents. Morpheus has the ACP checkout (off by default), a UCP manifest with `capabilities: {}`, Web Bot Auth, llms.txt + feeds, MCP cart/checkout servers that need a merchant-issued token, and 3 WebMCP tools. Note: OpenAI pulled back ChatGPT Instant Checkout in March 2026 (about a dozen Shopify merchants live), so redirect-to-merchant-checkout is the realistic default; UCP (Google, Jan 2026, Shopify/Etsy/Target/Walmart) is the protocol to implement.
- **Over-promising:** about 18 of 92 default apps admit in their own `help.md` that they show nothing or change nothing (ai_stylist, rails, media_3d, drops, discovery_quiz, lookbook teaser, localization languages, post_purchase emails, returns_portal customer flow, b2b pricing, shipping tiers, motion, personalisation screen, newsletter composer, draft-order pay page, inventory stock page, tax Stripe adapter, importers' Magento/BigCommerce claim).
- **Velocity is high and corrective:** 190 releases in 60 days, 105 patch vs 85 minor, 217 `fix` vs 146 `feat` commits, one author; about a third of recent minors went to per-store verticals. That is the "unfinished" feeling: the shared engine's second layer was never the focus of a sprint.

## Comparison matrix

Legend: ✅ working product · 🟡 partial / model without consumer · ❌ absent. Sources: code audit (ours), docs.medusajs.com + releases, docs.saleor.io + changelog, shopify.com/news editions + shopify.dev/docs/agents + ucp.dev.

| Area | Morpheus v0.148 | Medusa v2.22 | Saleor 3.23 | Shopify 2026 | planned |
|---|---|---|---|---|
| Catalog: variants/options | 🟡 any axes in the model, flat variant rows in the form, no option matrix | ✅ options → variants | ✅ product types + attributes (reference/swatch/file) | ✅ 2048 variants, combined listings |
| Bundles / kits | ❌ `'bundle'` is a label, no components, no stock | 🟡 recipe | ❌ | ✅ bundles |
| Rule-based collections | ❌ manual only (Shopify smart collections import as manual) | 🟡 | ❌ | ✅ smart collections, AI collection sort |
| Per-channel availability | ❌ `Product.channels`, `ProductChannelListing` unused | ✅ sales channels | ✅ channels: price, availability, publication | ✅ markets + channels |
| Product translations | ❌ stored (`localized_translations`), never rendered | 🟡 Translation module, experimental | ✅ full | ✅ Translate & Adapt |
| Metafields / attributes | ✅ metafields on 6 objects; 🟡 attributes no UI | ✅ | ✅ attributes, models (3.22) | ✅ metafields + metaobjects |
| Price lists / customer-group pricing | ❌ `b2b.PriceList`, `markets.ProductMarketPrice` have no consumer ✔ | ✅ Pricing module, price lists, rules; 10× faster calc (v2.18) | 🟡 per-channel pricing | ✅ B2B price lists, volume pricing |
| Multi-currency / FX | 🟡 `localized_prices` applied at cart-add; `ExchangeRate` manual, no feed, no rounding | ✅ regions + currencies | ✅ per channel | ✅ Markets, duties |
| Tax-inclusive display | ❌ `prices_include_tax` has no reader ✔ | ✅ | ✅ | ✅ |
| Omnibus 30-day prior price | ✅ `PriceHistory` | ❌ | ❌ | app |
| Promotions | 🟡 engine has percent/fixed/free-ship/bogo/tiered/gift; coupon scope unread ✔, `first_order` never excludes ✔, `customer_groups` iterates a manager ✔, BxGy coupon = 0, no UI, no budgets | ✅ rules, campaigns + budgets, buy-X-get-Y target strategy (v2.22.5) | ✅ catalogue + order promotions with predicates, gift reward; no BxGy, voucher excludes order promo | ✅ Functions, combinations, automatic + codes |
| Gift cards / store credit / loyalty | ✅ tenders ordered after tax+shipping; 🟡 no manual credit screen, tier perks unapplied | ✅ Gift Card + Store Credit modules (v2.14), Loyalty module | ✅ gift card as payment (3.23) | ✅ store credit |
| Inventory | 🟡 fail-closed reservations ✅; warehouses + allocator without a screen; backorder blocked at reserve ✔; simple products untracked; no transfers | ✅ Inventory + Stock Location, reservations, events (v2.18), CSV export (v2.19) | ✅ warehouses, allocation strategies, click & collect, warehouse→channel (3.23) | ✅ multi-location, transfers, states |
| Checkout | ✅ guest, multi-step + one-page, Stripe PE + Express (Apple/Google/Link), PayPal, COD, bank; ❌ notes/gift/T&C, no field hook, no pickup | ✅ cart/checkout API, 45 payment integrations, Adyen beta (v2.22.2) | ✅ Transactions API, Stripe/Adyen/Hyperswitch apps, `deliveryOptionsCalculate` | ✅ Checkout Components (GA), Shop Pay, 7 new local methods |
| Authorize → capture | ❌ base `capture()` only ✔ | ✅ | ✅ | ✅ | planned |
| Saved card at checkout | ❌ `PaymentIntent` has no `customer` | ✅ | ✅ stored methods | ✅ |
| Order editing after placement | ❌ | ✅ order changes (edits, exchanges, claims), versioned timeline | 🟡 lines on drafts, discounts after placement | ✅ |
| Partial / multiple fulfilments | 🟡 models yes, form fulfils everything | ✅ | ✅ per warehouse | ✅ |
| Shipping labels / carriers | ❌ Shippo/EasyPost for quotes only; no labels | ✅ 17 fulfilment integrations | 🟡 apps | ✅ labels, Shop Promise |
| Shipping rate configuration | 🟡 flat only in UI; tiers and free-over exist in the engine but cannot be entered; USD-only new rates | ✅ shipping options + profiles | ✅ zones, price/weight | ✅ |
| Returns / exchanges | 🟡 return → approve → receive → refund/credit for staff; no customer screen; exchanges modelled, not built | ✅ returns, exchanges, claims | ✅ returns/replacements, refund reasons (3.22/3.23), grant-refund flow | ✅ self-serve returns + exchanges |
| Refunds | ✅ idempotent, original tender, store-credit option; 🟡 amount-only form | ✅ | ✅ draft/finalize with permissions, split across methods | ✅ |
| Draft orders / payment link | 🟡 build + convert; no pay page or invoice email | ✅ draft → order | ✅ drafts | ✅ |
| B2B | 🟡 companies, buyers, price lists, quotes, net terms exist; none affect checkout ✔ | ✅ starter: companies, employees, spending limits, RFQ, approvals | 🟡 customer types + attributes (Aug 2026) | ✅ companies, net terms, volume pricing |
| Subscriptions | ✅ Stripe Billing, dunning, trials; 🟡 no self-serve cancel/pause | 🟡 recipe | ❌ | apps |
| Marketplace / vendors | ✅ portal, split, payouts; ⚠ vendor credited on `ORDER_PLACED` before payment, never reversed | 🟡 recipe | ❌ | Collective / Product Network |
| Tax | 🟡 regions + rates; category rates impossible (`tax_category_code` missing) ✔, `is_taxable` ignored, pre-discount base, no shipping tax, no VIES/OSS/provider | ✅ Tax module + providers | ✅ tax classes, AvaTax app, exemption metadata (Apr 2026) | ✅ Shopify Tax |
| Customers / segments | ✅ accounts, OTP, addresses, wishlist, GDPR; 🟡 RFM segments only, no groups/tags, no social login | ✅ customer groups | 🟡 customer types (Aug 2026) | ✅ segments |
| Marketing email / SMS | 🟡 SMTP only, newsletter without composer, cart-abandonment drip ✅, post_purchase scheduled but never sent ✔, no "email customer" workflow action, no SMS, push unsent | 🟡 notification providers (SendGrid, Resend, Klaviyo) | 🟡 SMTP + Customer Emails apps, Klaviyo | ✅ Shopify Email, Flow, Campaign Autopilot |
| Search | 🟡 substring default; Postgres FTS only in GraphQL; semantic = Python cosine over JSON; Typesense coded but not installable | ✅ Search module (PG provider, v2.21) + Algolia/Meili | ✅ PG search vectors: prefix, boolean, accents, rank (3.23) | ✅ AI search with typo tolerance |
| Headless API | 🟡 36 queries / 50 mutations; no customer auth, cookie carts, no pagination/facets, STABLE doc names wrong ops, schema not CI-gated | ✅ Store API, JS SDK, Next.js starter | ✅ full GraphQL incl. accounts, storefront starter, App SDK 1.0 | ✅ Storefront API, Hydrogen GA for any framework |
| Extension model | ✅ hooks + contributions + disable-safety + signed component updates (early) | ✅ modules, workflows with compensation, plugins, admin extensions | ✅ Apps (webhooks + iframe), Configurator (config as code) | ✅ Functions, app store |
| Admin | ✅ hubs, Cmd+K, Linda on every page, dark mode; ❌ stock screen, promo CRUD, custom reports; RBAC log-only | ✅ list views, exports; RBAC = Enterprise licence | ✅ global search, widgets, Pulse analytics (Jul 2026) | ✅ Sidekick as operator, Canvas, Rollouts, A/B | planned |
| Agentic commerce (shopper side) | 🟡 ACP checkout off by default; UCP manifest empty; MCP cart/checkout need a merchant token; Web Bot Auth ✅; llms.txt + feeds ✅; 3 WebMCP tools | 🟡 ACP tutorial, community UCP plugin | 🟡 ACP Instant Checkout app (beta) | ✅ UCP default-on, Catalog/Cart/Checkout/Order MCP, WebMCP everywhere, agent trust tiers, knowledge base | planned |
| Agentic (merchant side) | ✅ Janus: ~235 tools, consent kernel, automations, external agents over MCP/GraphQL | 🟡 Cloud MCP read-only (Oct 2026) | 🟡 MCP read-only (Nov 2025) | ✅ Sidekick + connectors to 9 agents | planned |
| Compliance | ✅ Omnibus, GPSR, AI Act Art. 50, consent kernel, WCAG, PCI 4.0.1 CSP, Turnstile | ❌ | ❌ | partial (duties, taxonomy) |
| i18n | 🟡 hr + sr UI catalogs; localized links; content translations not shown on products | 🟡 experimental | ✅ | ✅ |
| Multi-store | ❌ one deployment per store | 🟡 sales channels | ✅ channels | ✅ |
| Ops / self-hosting | ✅ safe_migrate, restore, rollback guard, health, error log, OTel opt-in; 🟡 backups local-only, updater inert in containers | 🟡 Cloud monitoring/log drains; self-host needs Redis + worker split | ✅ OTel native, Cloud | SaaS |

## Where we are weak — ranked by what a merchant hits first

Evidence paths are under `plugins/installed/` unless noted. ✔ = re-verified by grep in this session.

1. **Tax computes wrong amounts.** `tax/services.py:121` reads `product.tax_category_code`, a field `catalog.Product` does not have ✔ → reduced rates (books!) can never apply; `compute_tax_for_cart` ignores `is_taxable` (gift-card SKUs taxed), taxes pre-discount amounts, never taxes shipping ("tax on shipping" does nothing), `TaxConfiguration.prices_include_tax` has no reader ✔, `is_compound` ignored; no VIES, OSS or provider (the `'stripe'` option is dead). An EU store files wrong VAT from day one.
2. **Coupon scope is not enforced and promotion eligibility is broken.** `marketing.Coupon.applicable_products/categories/collections/exclude_sale_items` have zero readers ✔; `buy_x_get_y` coupons discount 0; `promotions/services.py:103` does `list(customer.groups)` on a related manager ✔ (TypeError swallowed → promotions skipped for signed-in shoppers); `:113` `first_order` reads a non-existent `order_count` ✔ so it never excludes; `category_slugs` documented, not implemented; `gift` records a product but nothing adds the free line; no exclusive/combinable flag; the dashboard promotions page is read-only and Linda creates percent-off only.
3. **No stock operations.** No dashboard screen to edit stock, manage warehouses, transfer or import (inventory `help.md:16`); `reserve_for_order` (inventory/services.py:60-100) never consults `inventory_policy='continue'` ✔ so a "backorder" product fails at checkout; a simple product with no variant row is untracked; `'transfer'` exists only as a movement type.
4. **Fulfilment and shipping are shallow.** `FulfillmentForm.save` fulfils every remaining line; one tracking number per order, typed by hand; Shippo/EasyPost quote only (`shipping/app.py:18` "stub adapters"), no labels; weight/price tiers and free-over exist in the engine but cannot be entered (shipping `help.md:22`); new rates are USD; no pickup/local delivery, profiles or dimensions. Owner note already on file: no selling store has a shipping rate.
5. **No order editing, and admin cancel does not refund.** Daily customer-service work is impossible; `cancel`/`mark_refunded` accept `source='*'`, so a delivered order can be cancelled.
6. **Four price stores, one wired.** `Product.localized_prices` is applied at cart-add; `b2b.PriceList` → `crm.Account`, `markets.ProductMarketPrice` and `core.ProductChannelListing` are never consulted; `PRODUCT_CALCULATE_PRICE` has one subscriber (ai_assistant) ✔ and receives no quantity, so no volume breaks; `ExchangeRate` is manual (R9 FX was skipped); market % adjustment does nothing.
7. **Payments stop at "charge now".** No gateway implements `capture()` ✔ (`payments/gateway.py:59`); checkout `PaymentIntent.create` passes no `customer`, so saved cards work only for subscriptions; `PAYMENT_FAILED` is never fired although Stripe's `payment_intent.payment_failed` is handled; COD/manual inherit a `refund()` that returns "Not implemented".
8. **The headless contract is wrong and incomplete.** `docs/API_STABILITY.md` freezes `checkoutComplete`, `cartAdd`, `/api/graphql/`, `/api/health/`; the real names are `completeOrder`, `addToCart`, `/graphql/`, `/healthz`. No customer register/login/me/addresses over GraphQL (allauth headless not installed, no JWT); carts are session-cookie-bound (`orders/graphql/mutations.py:117` ignores `session_key`); `products` is a flat list capped at 100 with no cursor, sort or facets; `customers/graphql/*`, `marketing/graphql/*`, `inventory/graphql/queries.py` are empty stubs; the schema is not diffed in CI; no OpenAPI (DRF read-only `/v1/*` only); no TS SDK; `api/idempotency.py` middleware is not registered.
9. **About 18 apps over-promise** (list in the Verdict). Concretely never-working: `post_purchase.process_due_steps` is defined (`tasks.py:25`) but in no beat schedule ✔, so tracking/review/NPS emails never go out; localization's language pages "have no effect"; `ai_stylist`, `rails`, `media_3d`, `drops`, `discovery_quiz` render nothing; `motion` settings change nothing. Owner's choice: finish them (Phase C).
10. **Returns have no customer flow and exchanges are not built** (`returns_portal/help.md:15`, `ReturnResolution` modelled only); no return labels.
11. **Draft orders and quotes cannot be paid.** No customer pay page or invoice email (draft_orders `help.md:23`); `b2b.send_quote` only changes state; `accept_quote` does not create an order; `NetTermsAgreement` has no effect.
12. **No marketing email engine.** SMTP only (no SendGrid/Mailgun/SES/Postmark/Resend API), newsletter has no campaign composer (`help.md:22`), workflows has 12 triggers but no "email customer" action (`workflows/models.py:14-36`), no SMS, web-push subscriptions stored but nothing sends.
13. **Search is weak by default.** `catalog/search/django_backend.py` substring on name + book fields; Postgres FTS only behind GraphQL `products(search:)`; `typesense` not in requirements and no setting, so unreachable; semantic search is Python cosine over JSON (`core/embeddings.py:91`); facets only from Typesense. Saleor 3.23 and Medusa v2.21 both shipped Postgres-native search with prefix/boolean/rank this year.
14. **RBAC is wired but off.** `enforcement_mode` default `log` (`core/authz.py:39`, `rbac/app.py:70`), no grant UI, rbac has 0 tests.
15. **Shopper-side agentic surfaces are closed.** `tools/call` on `/mcp/storefront|cart|checkout/v1/` needs a merchant-issued Bearer; `agentic_checkout` and its `payments_enabled` are off by default; `/.well-known/ucp` reports `capabilities: {}` and `agent_mcp/well_known.py:13,72` says the UCP REST checkout is not implemented; no structured "store facts" for agents beyond llms.txt (Shopify's knowledge base: return window, shipping destinations); `docs/AGENT_PROTOCOLS.md` still says ACP `complete` returns `unsupported`.
16. **Webhooks are fragile.** 7 retries within ~1 minute then DLQ (`webhooks_ui/tasks.py:16`), HMAC without a timestamp (replayable), event names free text, idempotency middleware dead.
17. **Catalog depth.** Bundles label-only, no duplicate action, bulk edit = status only, no option-matrix UI, no `publish_at`, no HS code / country of origin, no dimensions, 12-column CSV without variants/images/stock, merchant review replies saved but never shown.
18. **Events with one end.** `PAYMENT_FAILED`, `CART_CREATED`, `CART_UPDATED` dead; `ORDER_CONFIRMED`, `PAYMENT_CAPTURED`, `KNOWLEDGE_SOURCES` (so RAG is unwired), `INVENTORY_OVERSTOCK_DETECTED` have no subscriber; no events for fulfilment created, shipped/delivered, order edited, stock adjusted, price changed, quote accepted, subscription lifecycle. `cart.item_added`/`checkout.started` fire from storefront views only, so headless/agent carts never reach the pixels.
19. **Money bugs outside the main path.** Marketplace vendors are credited on `ORDER_PLACED` (before payment) and never debited on cancel/refund, with a non-atomic read-modify-write; `LoyaltyTier.perks` computed, never applied; guests earn no points.
20. **Tests and docs lag the code.** rbac 0 tests, promotions 2, b2b 2, importers 2, 20 apps under 5; coverage gate 40 %; no E2E (axe/Lighthouse audit live pages only); 30-entry plugin-standard baseline; README frozen at v0.123 (claims Magento/BigCommerce importers that do not exist, "restore by hand" after v0.120 shipped restore), ~10 plan files with stale status lines, 108 plugin→plugin baseline pairs, 10 hard-coded `book_product` imports in `storefront/views/catalog.py` (guarded, not contributed).

## Where we are ahead (keep, do not regress)

- Fail-closed stock reservation inside the checkout transaction + Redis cart hold + unpaid-order expiry that releases stock and every tender.
- `CART_CALCULATE_BREAKDOWN` ordering (discount 10 → tax 20 → shipping 30 → member 40 → points 45 → credit 46 → gift card 50) and pro-rata tender re-credit on refund.
- One validated price seam (`core/pricing.py`) for displayed and charged price.
- `PriceHistory` Omnibus; GPSR; Art. 50 marks; consent kernel honoured by CAPI/GA4/audiences; payment-page nonce CSP; Turnstile on public forms.
- Protected FSM with central hook firing and `OrderEvent` log; idempotent refunds through the original gateway with affiliate/points/gift-card clawback.
- Digital delivery (tokens, library, withdrawal waiver, audiobooks), subscriptions on Stripe Billing with dunning, affiliates, marketplace split + portal, dropshipping suppliers, 9 channel feeds + CAPI.
- Janus: one gate chain for chat/widget/automations/external agents, consent only from the merchant's own message, 36 scopes, AI-Act report, provenance.
- Safe deploys: pre-deploy backup, migration gate, restore engine with closed-sign, per-store rollback guard, deploy-smoke + live axe/Lighthouse.
- Disable-safety: contributions, hook gating by active plugin, boundary ratchets at core 0 / plugins 108 and shrinking.

## Plan — release sequence

Order follows the owner's lens (general engine first) and dependencies. One release in flight at a time; sizes are dev-days. Every release: `manage.py release --minor|--patch`, `help.md` of each touched app, a Linda tool per merchant action (`requires_approval=True` on writes, scope in `AVAILABLE_SCOPES` and `gates.LINDA_SCOPES`), settings keys with readers, both ends of every new event, migrations that leave v−1 working, `check_plugin_standard.py --save` when a thin app gains tests.

### Phase A — engine correctness (≈7–8 weeks; sizes in dev-days)

| # | Release | Goal | Size | Depends on | Status |
|---|---|---|---|---|---|
| A1 | Tax correctness | category rates reachable, `is_taxable` honoured, discount-aware base, shipping tax, inclusive prices, compound | M 3 | — | live, v0.149.0 |
| A2 | Promotions & coupons | eligibility bugs, coupon scope, BxGy, gift line, `combinable`, dashboard CRUD, Linda CRUD | L 5 | — | v0.150.0 live: `promotions.update` covers switching off (no separate deactivate tool); the cart summary does not list the gift yet (the order does); a coupon's minimum still compares the whole subtotal |
| A3 | Inventory operations | stock card, warehouses page, transfers, backorder policy, default variant, CSV stock | M 3 | — | v0.152.0 live |
| A4 | Fulfilment & shipping rates | partial fulfilment, per-shipment tracking/email, labels, rate editor, pickup | L 5 | — | v0.154.0 live: labels are a shipping-owned `ShippingLabel` (no Fulfillment columns, no stored carrier rate id: each label buys a fresh shipment's rate, by `label_rate` since v0.155.0); GraphQL `markOrderFulfilled` and agent_core's `orders.mark_fulfilled`/`mark_shipped` record a parcel since v0.182.0 (P8); no theme shows a parcel's tracking on the account order page yet |
| A5 | Payments | Stripe manual capture, saved cards at checkout, `PAYMENT_FAILED`, `ORDER_CONFIRMED` subscriber, offline refunds | M 3 | A4 | v0.155.0: `capture_mode` (immediate, first/last parcel, manual), hold sweep, Charge now + `payments.capture`, saved cards by two settings, `PAYMENT_FAILED` on the timeline, refunds `settle` (store credit, external); A4 settings `label_rate`, `parcel_emails`, `fulfil_marks_shipped`. No `ORDER_CONFIRMED` email (nothing to say before the charge; the placed email already went) and no failed-payment email (A8, it needs the pay link); `save_card` at checkout is the Element's own box, not an A7 field |
| A6 | Pricing seam | one resolution order, `quantity`/`request` kwargs, b2b + markets subscribers, ECB FX, minor-unit rounding | M 3 | — | planned |
| A7 | Checkout fields | `CHECKOUT_FIELDS` hook + notes / gift / T&C / opt-in / save-card; dead cart events removed | M 2 | — | v0.168.0: one filter (`core/checkout_fields.py`, kwargs `user`), checked by `completeOrder` (no separate validate filter); orders' note / gift message / terms and newsletter's opt-in (newsletter owns the list, so not customers' `accepts_marketing`); `allow_guest_checkout` read again (sign-in first, `SIGN_IN_REQUIRED`); wallets step aside for a required field. `save_card` stays the Element's own box (A5). `CART_CREATED`/`CART_UPDATED` kept: removing an SDK event name is a break (`check_api_stability.py`). ACP skips both checks |
| A8 | Payment link | `/pay/<token>/`, draft-order email + Linda tool, failed-payment retry email | S 2 | — | v0.171.0 live |
| A9 | B2B | price lists live, quote email → accept → order, net-terms gateway, VAT-ID + reverse charge | L 4 | A1 A6 A7 A8 | planned |
| A10a | Cancel and refund rules | `cancel_with_refund`, FSM narrowed (the "Cancel gap" part of A10 below) | S 1–2 | A5 | v0.180.0, live |
| A10b | Order editing | `orders/editing.py`, payment delta, `ORDER_EDITED`, dashboard screen | L 4 | A3 A5 A8 A10a C4 | planned, order #13 |
| A11 | Marketplace money | vendor credit on `ORDER_PAID`, reversal on cancel/refund, atomic balance | S 1 | — | planned |

Cross-cutting facts from the architecture pass: `CART_CALCULATE_BREAKDOWN` runs promotions 10 → tax 20 → shipping 30 → subscriptions 40 → loyalty 45 → store_credit 46 → gift_cards 50 → eco 60, which is why shipping can never be taxed (A1 moved tax to 42, after shipping and the member discount, and updated the CLAUDE.md order paragraph in the same commit). `rbac/models.py:44-51` already holds `b2b.read/write` and `marketing.read/write` (the CLAUDE.md sentence "there is no `marketing.*` capability" is stale and is corrected in A2).

**A1 · Tax correctness (minor, M).** `tax/models.py`: `ProductTaxCategory(product OneToOne → catalog.Product, category FK → TaxCategory)` — tax owns the link (one concept = one owner, no catalog→tax coupling) — and `TaxConfiguration.shipping_taxable` (`default=False, db_default=False`). `tax/services.py:compute_tax_for_cart`: read the category through the OneToOne (replaces the dead `hasattr(product, 'tax_category_code')` at :121); skip a line when `variant.is_taxable` (else `product.is_taxable`) is False; taxable base = line amount minus its pro-rata share of `value['discount']` (pass `discount` in from `app.py`); with `shipping_taxable`, tax the shipping amount at the region's standard rates; with `prices_include_tax`, tax = gross − gross/(1+Σ rates), kept out of `value['tax']` (every later handler recomputes the total from it) and carried as `meta['tax_included']` lines; `_resolve_rate` → `_resolve_rates` ordered by `priority`, every rate applies, `is_compound` taxes the running base. `tax/app.py:on_cart_breakdown` priority 20 → 42 (after the member discount at 40, before the tenders). `orders/services.py:_order_metadata` copies `tax_included`; invoice prints "Includes VAT" or the tax lines. `tax/dashboard.py` re-exposes `prices_include_tax` and the new flag (both now have readers); `shipping/dashboard.py:114` + `shipping.html:187` drop the no-op "tax shipping" checkbox. No copy of the old `PluginConfig['tax_shipping']`: nothing ever read it, so a store that ticked it never charged tax on shipping, and the new switch starts off to keep totals as they are. Tax-category select on the product form via `PRODUCT_FORM_CARDS`/`PRODUCT_FORM_SAVED` (pattern `book_product/app.py:141-161`). Migration tax 0002: CreateModel + AddField (db_default) — additive, v−1 ignores both. `tax.delete_category` deletes the category's rates first (`TaxRate.category` is SET_NULL, which would turn a reduced rate into one more standard rate). Tests `tax/tests/test_cart_tax.py` (non-taxable skipped, discount base, shipping taxed only with the flag, inclusive math, compound, tax priority > shipping's; `_handlers` saved/restored with `addCleanup`). Linda `tax.set_category`, `tax.set_product_category`, `tax.update_settings` (approval); no delete-category tool, because a delete moves every product in it to the standard rates and drops its rates, so it stays a staff action. help.md tax + shipping. Risk: totals change on carts with discount + shipping (today tax ignores the discount, so stores overcharge) — release note. Live probe: a reduced-rate book in a dotbooks cart.

**A2 · Promotions & coupons (minor, L).** `promotions/services.py:_matches`: `customer_groups` → `customer.groups.values_list('name', flat=True)` (today `list(manager)` raises and the swallowing `except` in `app.py` skips every promotion for signed-in shoppers); `first_order` → `customer.purchase_count == 0 and not customer.orders.exclude(status='cancelled').exists()` (`purchase_count` exists, `customers/models.py:64`); implement `category_slugs` through `catalog/category_tree.py` (subtree rule); each promotion evaluated in its own try so one bad rule skips itself only. `promotions/app.py:on_cart_breakdown` coupon block: eligible subtotal = lines in `applicable_products` ∪ subtree of `applicable_categories` ∪ `applicable_collections`, minus lines with `compare_at_price` when `exclude_sale_items`; percent/fixed apply to that base (fixed capped at it); `buy_x_get_y` reuses `services._apply_bogo` with new `Coupon.buy_quantity/get_quantity` (`db_default=1`); `gift` → `meta['gift_lines']`, and `orders/services.py:create_from_cart` appends a zero-priced `OrderItem` per gift line where it reads `applied_promotions`; the cart summary shows "Free gift". `Promotion.combinable` (`default=True, db_default=True`): a non-combinable promotion applies only when nothing applied before it and stops evaluation. Dashboard CRUD in the owner app: `promotions/forms.py:PromotionForm` (shape of `admin_dashboard/forms/marketing.py:CouponForm`), views `promotion_new/edit/toggle` in `promotions/views.py`, URLs, template; gate `require_capability('marketing.write')`. Migrations: promotions 0002 AddField, marketing AddField ×2 — additive. Tests `test_eligibility.py`, `test_coupon_scope.py`, `test_bxgy.py`, `test_gift_line.py`, `test_combinable.py`, the boundary trio on the form views, tool tests (promotions goes from 2 tests to 20+; `check_plugin_standard.py --save`). Linda `promotions.create` (kind, value, predicates), `promotions.update`, `promotions.deactivate` (approval; `create_percent_off` kept). help.md promotions + marketing. Risk: scoped coupons stop discounting the whole cart — release note. Live probe: a category-scoped coupon on an out-of-scope cart refuses.

**A3 · Inventory operations (minor, M).** `inventory/services.py:reserve_for_order` (:60-100): when the plan is short and `variant.inventory_policy == 'continue'`, reserve what exists and record the backordered remainder in the `reserve` movement (reserved count first in the note — `_qty_from_note` reads the first integer), `order.log_event('BACKORDERED')`. Default variant: `catalog/variants.py:ensure_default_variant(product)` (nothing creates variant rows for simple products today); `orders/services.py:CartService.add_item` uses the single active variant when `variant_id` is None and the product is not `variable`, so the line is reservable. Stock card: `inventory/app.py` subscribes `PRODUCT_FORM_CARDS` (active variant × active warehouse quantity inputs) and `PRODUCT_FORM_SAVED` (writes through `StockMovement.record(..., 'adjustment')`), firing new `STOCK_ADJUSTED` whose subscriber (inventory) closes an open `StockoutAlert` when available > 0 — both ends. Warehouses page: `inventory/dashboard.py` + `urls_dashboard.py`, `DashboardPage(nav='settings', section='shipping', slug='warehouses')`, dispatch like `shipping/dashboard.py:zones`; `InventoryService.transfer(variant, src, dst, qty, reference)` atomic, two `transfer` movements. CSV: optional `stock` (+ `warehouse_code`) column in `importers/adapters/csv_products.py` that fires filter `INVENTORY_SET_STOCK` (inventory answers; importers never import inventory; column ignored when inventory is off). No migrations. Tests `test_backorder_policy.py`, `test_default_variant.py`, `test_stock_card.py` + disable guard, `test_warehouses_page.py` boundary trio, `test_transfer.py`, `importers/tests/test_csv_stock.py`. Linda `inventory.set_stock`, `inventory.transfer_stock`, `inventory.create_warehouse` (approval). help.md inventory (replace the "no dashboard page" paragraph). Risk: the Redis cart hold (`cart_reservations.py`) stays advisory; order-time reservation is the gate.

**A4 · Fulfilment & shipping rates (minor, L).** Move `admin_dashboard/forms/orders.py:FulfillmentForm.save` logic to `orders/fulfilment.py:create_fulfillment(order, lines: {item_id: qty}, tracking…)` shared by the form, Linda and the dropshipping apps; the form builds `qty_<item_id>` fields from remaining quantities; partial → new FSM transition `fulfill_partially` (target `partially_fulfilled`, no migration); all remaining → existing `ship()/fulfill()`. Events: `FULFILLMENT_CREATED` fired by `create_fulfillment`, subscriber `core/emails/handlers.py` sends a per-shipment email with that shipment's tracking only while the order is not fully fulfilled (the last shipment keeps the `ORDER_FULFILLED` email — never two); `ORDER_DELIVERED` added to `orders/signals.py:_TARGET_EVENTS`, subscriber `post_purchase/handlers.py` re-anchors follow-ups. Labels: `shipping/services.py:purchase_label(fulfillment)` for `carrier_shippo` (transactions) and `carrier_easypost` (buy); `on_cart_breakdown` stores `meta['carrier_rate_id']`, `_order_metadata` copies it; `Fulfillment.label_url`, `label_provider_id` (CharField `db_default=''`); buy/open-label links through an `ORDER_DETAIL_PANELS` panel owned by shipping. Rate editor: `shipping/dashboard.py:_create_rate/_edit_rate` parse `tiers` rows and `free_threshold`; amounts built with the store currency (`plugins/dropshipping/importer.py:store_currency()`), never USD; new computation `pickup` (0 or flat). Dimensions and shipping profiles deferred (carriers quote by weight today). Migrations: orders AddField ×2 (db_default); shipping AlterField choices. Tests `orders/tests/test_partial_fulfilment.py`, email once-only test, `shipping/tests/test_rate_editor.py`, `test_labels.py` (HTTP mocked), `test_pickup.py`. Linda `orders.fulfill_lines`, `shipping.set_rate`, `shipping.buy_label` (approval). help.md orders + shipping. Risk: `themes/test_shipping_claims.py` — the free-progress block keeps reading `free_threshold`.

**A5 · Payments (minor, M; after A4).** `payments/app.py` key `capture_mode` (reader: Stripe service). `payments/services/stripe.py:create_payment_intent`: `capture_method='manual'` when set; `customer=get_or_create_stripe_customer(order.customer)` for signed-in shoppers (saved cards appear in the Element; `checkout_payment` mints a CustomerSession secret); `setup_future_usage='off_session'` when `order.metadata['save_card']` (writer in A7). `process_webhook` handles `payment_intent.amount_capturable_updated` → transaction `authorized`, `order.payment_status='authorized'`, `OrderService.confirm_order()` — `ORDER_CONFIRMED` gets its first subscriber (core/emails "reserved, charged when it ships"). `StripeGateway.capture()` overrides `gateway.py:59` → `PaymentIntent.capture` → `_mark_transaction_success` → `ORDER_PAID`; payments subscribes `FULFILLMENT_CREATED`/`ORDER_FULFILLED` to capture. `orders/tasks.py:expire_pending_orders` excludes `authorized`; new beat `payments.void_stale_authorizations` (day 6; Stripe expires at 7), registered by name in `CELERY_BEAT_SCHEDULE`. `_mark_transaction_failed` fires `PAYMENT_FAILED` (payment, order, error); subscriber `orders/app.py` logs the timeline event (A8 adds the retry email). Offline refunds: `RefundService.process(settle='gateway'|'store_credit'|'external')` — store credit through `orders/store_credit.issue` with a distinct reference (so `recredit_refund` does not double-count) + `Refund(is_processed=True)` + `PAYMENT_REFUNDED`; `order_refund.html` offers the choice when `gateway.supports_refunds` is False. Migration: payments AlterField choices. Tests `test_manual_capture.py`, `test_saved_card_intent.py`, `test_payment_failed_event.py`, `orders/tests/test_offline_refund.py`. Linda `payments.capture` (approval), `orders.refund` gains `settle`. help.md payments + orders.

**A6 · Pricing seam (minor, M).** `core/pricing.py:apply_price_filter(price, *, product, customer=None, quantity=1, variant=None, request=None)` forwards the kwargs (`ai_assistant/app.py:303` already takes `**kwargs`); callers pass what they have: `orders/services.py:_resolve_unit_price` and `CartService.add_item` (quantity, variant), GraphQL `update_cart_item` re-resolves on quantity change, `catalog/graphql/types.py` resolvers pass `info.context.request`, `storefront/templatetags/pricing.py` passes `context['request']`. Resolution order by priority: **b2b 10** (`b2b/app.py` subscribes; `resolve_price_for_account` gets its first caller: customer → `crm_accounts` → `PriceListItem` with the largest `min_quantity ≤ quantity`, same currency only — the seam rejects swaps), **markets 20** (`markets/app.py` subscribes with `services.price_for(product, request.market)`; `MarketMiddleware` seeds `session['display_currency']` from the market when unset so the existing `localized_prices` path quotes in the market currency), then orders' localized fallback, then base; `ai_assistant` stays 50. `PriceListItem.min_quantity` (`default=1, db_default=1`), unique constraint widened. FX: `markets/tasks.py:fetch_ecb_rates` daily beat (eurofxref via `core.net.outbound_request`, cross-rates from the store currency, `source='ecb'`, manual rows never overwritten), setting `fx_auto_update` with the task as reader (the parked R9). `core/pricing.py:convert()` quantizes to the currency's minor unit (JPY), used by `convert_money`. Scopes: add `markets.read/write` to `agent_mcp/scopes.py:AVAILABLE_SCOPES` + `_CAPABILITY_FOR_SCOPE` and to `gates.LINDA_SCOPES` (`b2b.*` is already in both, `scopes.py:135`, `gates.py:57`); a tool scope missing from the vocabulary falls back to wildcard (landmine). `core.ProductChannelListing` is left alone: it has no callers but is the channel spine ADR 0018 (multi-storefront, approved) would use — **owner decision at execution: keep for ADR 0018 or retire in two releases**. Migration: b2b AddField. Tests `core/tests/test_pricing_seam_kwargs.py`, `b2b/tests/test_price_list_seam.py`, `markets/tests/test_market_price_seam.py`, `test_ecb_task.py`, `orders/tests/test_cart_reprice_on_qty.py`, `core/tests/test_convert_minor_units.py`. Linda `b2b.set_price_list_item`, `markets.set_product_price`, `markets.refresh_rates` (approval). help.md markets, b2b, orders. Risk: b2b prices must never enter the anonymous GraphQL response cache (the key is query+variables, not viewer) — the b2b subscriber returns the input price when `customer is None`.

**A7 · Checkout fields (minor, M).** `core/hooks.py`: `CHECKOUT_FIELDS` (filter; value = list of `{key, label, kind, required, help, order}`; kwargs request, cart) and `CHECKOUT_FIELDS_VALIDATE` (filter; value = error list; kwargs post, fields). `storefront/views/checkout.py:checkout_review` and `checkout_one_page.py` fire both; declared keys travel in GraphQL `CompleteOrderInput.checkout_fields` → `OrderService.create_from_cart(extra_metadata=…)` → `metadata['checkout_fields']`. Tag `{% checkout_fields %}` (`storefront/templatetags/checkout.py`) renders generically inside the checkout `<form>` of `checkout_review.html` and `checkout_one_page.html` in all five themes; guard `themes/test_checkout_fields.py` (every theme, both forms — the `core/tests/test_bot_check.py` shape). Built-in subscribers, each owner also subscribing `ORDER_PLACED` to act: orders — `order_notes` (→ `customer_notes`), `gift_message` (packing slip prints it), `terms_accepted` (required; setting `checkout_terms_url`); customers — `marketing_opt_in` (→ `accepts_marketing`); payments — `save_card` for signed-in Stripe shoppers (→ `metadata.save_card`, read by A5). Settings keys sit in each owner's schema with the handler as reader. Housekeeping: delete the dead `CART_CREATED`/`CART_UPDATED` constants. No migrations. Tests `storefront/tests/test_checkout_fields.py`, `themes/test_checkout_fields.py`, `orders/tests/test_checkout_fields_metadata.py`, customers opt-in. Linda: none (settings panels; stated). help.md orders, customers, payments. Known limit: ACP/UCP checkouts never see a required T&C field (validation runs in storefront views) — documented.

**A8 · Payment link (minor, S).** `storefront/views/checkout.py:pay_order(request, token)` at `/pay/<token>/`: order by `public_token` (constant-time, as `order_confirmation`), refuses paid/cancelled, amount due = total − succeeded transactions − refunds, `PaymentService.create_payment_intent(amount=…)` (idempotency key already includes the amount), renders `checkout_payment.html` with the order summary; offline gateways show instructions. `draft_orders/views.py:send_payment_link` converts (existing `convert_to_order`) and emails `emails/payment_link.html` through `core.emails.send_templated_email`; `order.log_event('PAYMENT_LINK_SENT')`. `PAYMENT_FAILED` (A5) gets its customer email with the link. No migrations. Tests `storefront/tests/test_pay_link.py`, `draft_orders/tests/test_payment_link.py`. Linda `draft_orders.send_payment_link` (approval). help.md draft_orders (replace "no page a customer can open").

**A9 · B2B (minor, L; after A1 A6 A7 A8).** `Quote.public_token` (CharField `db_default=''`, set on save like `orders/models.py:_gen_public_token`); `b2b/services.py:send_quote` emails `emails/quote_sent.html` with `/b2b/quote/<token>/`; storefront view `b2b/views_quote.py` (lines, Accept/Decline). `accept_quote` builds a `DraftOrder` and calls `draft_orders.services.convert_to_order` (declare `draft_orders` in b2b's `requires`), fires `QUOTE_ACCEPTED` (subscriber core/emails notifies `quote.owner`); then an active `NetTermsAgreement` within `credit_limit` → order placed with `payment_gateway='net_terms'` and `metadata['due_at']`, else the A8 payment link. `b2b/gateways.py:NetTermsGateway` registered in `ready()`, offered only to customers whose account has terms; `orders/tasks.py:OFFLINE_GATEWAYS` += `'net_terms'`; beat `b2b.net_terms_reminders`. VAT ID: tax contributes a `CHECKOUT_FIELDS` field `vat_number` (tax setting `collect_vat_id`), validated by `tax/vies.py` (`outbound_request`, 24 h cache), copied into `billing_address['vat_number']`; `tax/services.py` zero-rates an intra-EU B2B cart with a validated ID and sets `meta['reverse_charge']`; the invoice prints the clause. Migration: b2b 0002 AddField (db_default). Tests `test_quote_flow.py`, `test_net_terms_gateway.py`, `tax/tests/test_reverse_charge.py` (VIES mocked); b2b goes from 2 tests to 20+. Linda `b2b.create_quote`, `b2b.send_quote`, `b2b.record_acceptance` (approval). help.md b2b rewritten (the "none of these change what a customer is charged" paragraph goes).

**A10 · Order editing (minor, L; after A3 A5 A8). Split on 2026-11-18:**
- **A10a** is the "Cancel gap" sentences below, released first and alone, with each new choice a setting under the rule of 2026-11-12: whether a staff cancel refunds, and what a customer cancel does with a paid order. A delivered order cannot be cancelled; that is a safety rule, not a setting.
- **A10b** is the rest, after C4.

`orders/editing.py`: `add_line / remove_line / set_quantity / recalculate` on orders with no `Fulfillment` and status in pending/confirmed/processing. `recalculate` builds a temporary `Cart` (`session_key=f'edit:{order.id}'`, lines, coupon by code, customer) and calls `calculate_cart_breakdown(..., address=order.shipping_address, shipping_rate_id=metadata['shipping_rate_id'])` — `_order_metadata` starts storing `shipping_rate_id`; new filter kwarg `editing=True` makes loyalty@45, store_credit@46 and gift_cards@50 return early (tenders are already on the order); totals copied back, temp cart deleted. Stock: `InventoryService.reserve_delta / release_line(order, variant, qty, reference=f'{order_number}#e{n}')` — inventory's `release_reservation` is keyed on `order_number` exactly, so release/commit must match the suffix scheme (test: cancel after an edit). Payment delta: unpaid → new total + payment link; paid & up → `payment_status='partially_paid'` + link for the difference; paid & down → `RefundService.process(amount=diff)`; authorized (A5) → capture ≤ auth, remainder by link. `ORDER_EDITED` (order, changes) with subscriber core/emails "your order was updated" (+ pay link when due). Cancel gap: `orders/services.py:cancel_with_refund(order, reason, actor)` used by `storefront/views/account.py:account_order_cancel`, `admin_dashboard/views_split/orders.py:order_action` (:333), `orders_bulk` (:699) and Linda `orders.cancel`; FSM narrowed: `cancel` excludes shipped/delivered/refunded/cancelled, `mark_refunded` excludes cancelled/refunded (`orders/models.py:315-322`, `test_state_machine.py` updated). Dashboard `order_edit` view + template (qty inputs, add by SKU like `draft_orders/views.py:line_add`), gate `orders.write`, link from `order_detail.html`. No migrations. Tests `orders/tests/test_editing.py` (totals with tenders excluded, stock delta, three payment states), `test_cancel_refunds.py`, FSM, boundary trio, email. Linda `orders.edit_lines` (approval). help.md orders.

**A11 · Marketplace money (patch, S).** `marketplace/services.split_order` credits vendors on `ORDER_PAID` (not `ORDER_PLACED`), debits pro rata on `PAYMENT_REFUNDED` and in full on `ORDER_CANCELLED` (idempotent per order/refund like `gift_cards/tests/test_refund_recredit.py`), balance updates with `F()` under `select_for_update`. Tests `marketplace/tests/test_vendor_credit_timing.py`. help.md marketplace.

Deliberately not added in Phase A: a `PRICE_CHANGED` event (`PriceHistory` + `product.updated` webhooks cover it) and a generic subscription lifecycle event (the Stripe reconciler owns state; add when a subscriber exists).

### Phase B — the headless contract (≈2 weeks)

- **B1 · API contract repair (patch).** Fix `docs/API_STABILITY.md` to the real operation and route names; add `scripts/check_api_stability.py` coverage of the GraphQL SDL (dump schema in CI, diff against a committed `api/schema.graphql`, fail on removed/renamed STABLE fields); register `api/idempotency.py` `IdempotencyMiddleware` for `/graphql/` mutations with an `Idempotency-Key` header; update `docs/AGENT_PROTOCOLS.md` (ACP `complete` no longer `unsupported`).
- **B2 · Catalog pagination + facets over GraphQL (minor).** Relay-style `productsConnection(first, after, sort, filter)` beside the flat `products` (kept, deprecated in the doc); facets through the existing `LISTING_FACETS` seam so book facets arrive without the API importing the vertical; `search:` through the same backend dispatcher as the storefront.
- **B3 · Customer identity over GraphQL (minor).** `customerRegister`, `customerLogin` (email OTP, reusing `core/auth/services.py`), `me`, `myOrders`, `myAddresses` + address mutations; session-less cart by `cartToken` (a signed token minted on `cartCreate`, accepted by every cart mutation, replacing the `session_key` the resolvers ignore); the sign-in path must fire `AUTH_SECOND_FACTOR` and end in Django `login()` (staff-MFA landmine) and `CUSTOMER_EMAIL_VERIFIED` on OTP. Scopes: `customers.self`. Tests with `enforce_csrf_checks=True` and no cookies (`api/tests_csrf_bearer.py` pattern).
- **B4 · OpenAPI + REST parity (minor).** `drf-spectacular` on `api/rest.py`, schema at `/api/schema/`, listed in `docs/MORPHEUS_API.md`; the REST viewsets gain the same pagination as B2. (From the parked R13.)
- **B5 · Webhooks hardening (minor).** `X-Morpheus-Timestamp` in the signature base + 5-minute tolerance documented; retries over 24 h (1 m, 5 m, 30 m, 2 h, 6 h, 12 h, 24 h) before DLQ; event names validated against `MorpheusEvents`; a typed event catalogue page under Settings → Developers generated from `core/hooks.py` docstrings. Single trigger rule stays (`webhooks_ui/tests/test_one_trigger.py`).

### Phase C — finish the half-built apps (owner's choice, ≈3–4 weeks)

One release per app, each with a storefront or dashboard surface that proves the setting does something (`test_settings_keys_have_readers` stays green by construction):

- **C1 · post_purchase (patch).** Register `post_purchase.process_due_steps` in `CELERY_BEAT_SCHEDULE` by its registered name (every 15 min), make the four email templates real `core.emails` templates, consent-gate marketing steps, a test that boots the beat schedule and asserts the name (pattern `core/tests/test_beat_schedule.py`). Marketing steps carry the one-click unsubscribe pair that `core/emails/tasks.py` already sets. Report clicks and orders, not opens. *As built (v0.189.0):* three emails (the tracking step is dropped: core's shipping email carries tracking), each a setting that starts off; review request and survey are marketing (`core.consent.allowed` + `JourneyOptOut`); a step 3 days late is skipped; links carry `utm_source=post_purchase` for the Attribution report; Linda changes the settings with `settings.set`.
- **C2 · workflows "email customer" + newsletter composer (minor).** New workflow action `email_customer(template, subject)` using cms `EmailTemplate`; newsletter gets a campaign composer (subject, richtext body, segment = RFM segment or "all opted-in", schedule) sending through `core.emails` with the existing double-opt-in list; Linda `newsletter.campaign_create` (approval). Provider APIs (SendGrid/SES/Resend) come as `EMAIL_TRANSPORT` providers in a later patch if SMTP relay limits bite.
- **C3 · localization (minor).** The storefront reads `core.i18n.Translation` (`core/i18n/models.py:12`) for product name/description/short_description and category/collection names on `/<lang>/` pages (one `translated()` helper used by the PDP, listing and the GraphQL dict builder); the language list stays the `MORPHEUS_LANGUAGES` env (`morph/settings.py:662`, resolved at import, so it cannot be a per-request setting) and the dashboard Languages page becomes a coverage report per language (how many products/pages carry a translation, links to the editor and to the AI bulk-translate) instead of a switch that does nothing; hreflang already follows. A shown translation that began as a machine draft carries F1's mark. Localization gets its first tests.
- **C4 · returns_portal customer flow + exchanges (minor).** `/account/orders/<n>/return/` (reason, lines, resolution: refund / store credit / exchange), status page, emails on approve/reject (wire the orphan `return.approved/rejected` events), exchange = new draft order linked to the return with a zero-payment path when values match; Linda `returns.approve/reject/receive` already or added. From 2026-11-18 (order #8), the customer side is built on F3's page, so a guest reaches it by order number and email as well. The return window, who pays the return shipping and whether exchanges are offered are settings (defaults: today's behaviour). Its tools are P10's returns batch.
- **C5 · lookbook + discovery_quiz + drops (minor).** Lookbook: dashboard editor (image, hotspots → products) + the PDP "worn with" block reading it; discovery_quiz: a quiz editor (questions → tag/collection weights) + the storefront quiz page that lands on a filtered listing; drops: `publish_at` on Product (one nullable field, `db_default` NULL) + a countdown block + the Drops page listing scheduled products. Each app gets ≥5 tests.
- **C6 · ai_stylist + rails + media_3d + motion (minor).** ai_stylist: the shopper chat widget on the storefront, through the Janus storefront agent with shopper tools only (scope-less tools never reach a storefront agent — `core/agents/base.py`), consent-gated; rails: render the configured rails in `home_after_rails` from the `dynamics` engine; media_3d: `<model-viewer>` block on `pdp_below_gallery` when a variant has a GLB upload (one FileField on ProductImage or a `Media3D` row), AR via Scene Viewer / Quick Look links; motion: the settings drive the theme's `prefers-reduced-motion` and reveal classes through a `global_head` style block. Each proves its settings.
- **C7 · personalisation + inventory + wishlist dashboard screens (patch).** Personalisation gets its tab (what it reorders, on/off); inventory's stock screen is A3; wishlist gets a read-only "most wished" tab.

### Phase D — agentic parity with Shopify 2026 (≈3 weeks)

- **D1 · Public storefront MCP (minor).** Anonymous `tools/call` on `/mcp/storefront/v1/` and `/mcp/cart/v1/` for read + cart tools (no writes to store data), rate-limited per IP and per verified agent (Web Bot Auth identity raises the limit — the "trust tier"); checkout stays token/ACP/UCP. Shopper tools are the existing 5 + cart 3, no new tool semantics.
- **D2 · UCP cart/checkout/order (minor, M).** `agentic_checkout/` is already a complete ACP REST surface over `orders.Cart` (`/acp/checkout_sessions` create/detail/update/cancel/complete, delegated Stripe token, quote-drift guard, `/.well-known/acp.json`); `agent_mcp/well_known.py:ucp_profile` advertises only the MCP shopping service and empty `capabilities`. Add `agentic_checkout/ucp.py` + `urls_ucp.py` at `ucp/`: `POST checkout`, `GET/PUT checkout/<id>`, `POST checkout/<id>/complete`, `GET order/<id>` as thin UCP-shape serializers over the existing `_get_cart/_add_line_items/_apply_buyer/_apply_fulfillment/_locked_complete` (one session model, two protocol faces); payment = redirect to the store's own checkout for untrusted agents (the post-March-2026 default), delegated Stripe Shared Payment Token for trusted ones; same `acp.checkout` scope and `payments_enabled` gate. `ucp_profile` fills `capabilities['dev.ucp.shopping.checkout']` and `payment_handlers` by asking a new `UCP_CAPABILITIES` filter that agentic_checkout answers only when enabled and payments are on (no import; an honest profile). Also fix the token page's hand-only grant for `acp.checkout` (`agent_mcp/dashboard.py`) that `agent_mcp/help.md` admits is broken, and update `docs/AGENT_PROTOCOLS.md`. Tests `test_ucp_checkout.py` (create/update/complete, drift 422), `test_ucp_profile.py` (claimed only when live).
- **D3 · Agent knowledge base (patch).** Structured store facts for agents (return window from returns_portal settings, shipping destinations from shipping zones, payment methods from payments, delivery times, contact) published in `llms.txt`, `/.well-known/ucp` and `/ai/products.json` metadata — all read from the owning apps, never typed twice (soft-404/claims rule: omit what no app can source).
- **D4 · ACP on by default when Stripe is configured (patch).** `agentic_checkout.enabled_by_default` follows `payments.is_configured('stripe')`; the manifest advertises `complete` only then.

**Changes of 2026-11-18:**
- **D3 comes first and is widened.** It adds UCP profile hygiene (claim only what is live), a check of the OpenAI feed's required fields, a re-push when a product changes, a crawler-class setting (search, assistant fetch, training; each allowed or refused in `robots.txt`) and two more WebMCP tools.
- **D2 is narrowed** to UCP cart transfer: the agent builds the cart, and the buyer pays on the store's own checkout. Native UCP checkout waits for the trigger in the order section.
- **D1 follows D3.**
- **D4 is held.**

### Phase E — platform hygiene (interleaved, patch each)

- **E1** RBAC: a grant UI (role → users, per channel) and an "enforce" switch with a dry-run report page listing what would be denied in the last 7 days from the log rows; rbac tests ≥ 20. Moved up to order #17 on 2026-11-18: a merchant's turn already narrows Linda to the staff member's role (`gates.person_scopes`) while the store enforces roles, so grants are what make that real.
- **E2** Search: Postgres FTS as the default backend for the storefront too (`SearchVector` with `unaccent`, prefix matching, rank) with facets from the DB; Typesense either added to `requirements.txt` + a setting or its code removed.
- **E3** Wave-2 merges still open (promotions ← marketing first, now that promotions has a UI from A2; then channels, dropshipping, AI 9 → 1) by the two-release removal recipe.
- **E4** Docs: README numbers measured by a committed script (`scripts/measure_readme.py`, new — the v0.76 measurement was ad hoc and is not in `scripts/`), importer claims corrected (CSV, Shopify, WooCommerce only), stale plan status lines fixed, `CHANGELOG.md` retired in favour of RELEASE_NOTES; the gap-analysis report itself lands in `docs/plans/` in this release.
- **E5** Off-site backups: `morph_backup --upload` to an S3-compatible bucket (`STORAGES['backups']`), encrypted with `age` or the bucket's SSE, nightly; health check "Last off-site backup < 36 h".
- **E6** psycopg 3 (own release, deploy-critical), `requirements.lock.txt` regenerated with `--upgrade`.

### Phase F — obligations and reach (added 2026-11-18)

Each row is an option inside Morpheus for any store. Its owner app is named below, along with its setting (today's behaviour as the default), its Linda tool and its `help.md` lines.

| # | Release | Goal | Size | Depends on | Status |
|---|---|---|---|---|---|
| F1 | AI marks on translations and images | the Art. 50 mark on AI-drafted translations; an image's AI tag survives the image proxy | S 1–2 | — | v0.177.0, live 2026-11-18 |
| F2 | Claims and legal copy check | generic green-claim check in the site audit; eco_impact copy; legal-guarantee notice; accessibility statement | M 2 | — | v0.178.0, live 2026-11-18 |
| F3 | Online withdrawal function | an order-keyed, guest-reachable "Withdraw from contract here" with a timestamped acknowledgement | M 3 | A10a | v0.181.0, live |
| F4 | Regional card gateway app | cards for stores whose entity Stripe does not serve; Monri first | M 3–4 | — | planned, order #11 |
| F5 | Delivery estimate at checkout | the rate's estimated days at checkout and in the order email | S 1 | — | planned, order #12 |
| F6 | Subscription cancel and pause by the customer | self-serve in the account | S–M 2 | — | planned, order #14 |
| F7 | Origin and HS code | customs data on products; an import-charges notice | S–M 2 | — | later |

**F1 · AI marks on translations and images (minor, S).**
- **Translations.** `localization/drafting.py` writes AI drafts with `is_machine_translated=True, reviewed=False`, and a person approves them. Once shown, nothing marks them.
  - Wherever a translation that began as a machine draft is shown, it carries the same mark as AI-written product text (`ai_content` through `core.agents.provenance`): `data-ai-generated` for that language and the graph's `digitalSourceType`.
  - As with product text, only the merchant clears the mark.
  - The storefront does not render content translations yet (C3). This release marks every place that shows one today; C3 inherits the rule.
  - *Correction found while building (v0.177.0):* the storefront has shown reviewed translations since v0.160.0, on product pages, experiences, places, hotels, events, CMS pages and journal posts. v0.177.0 marks all of them.
- **Images.**
  - Morpheus generates no images; no image generation was found in v0.176.0.
  - An uploaded image whose IPTC/XMP metadata declares `digitalSourceType` `trainedAlgorithmicMedia` (or `compositeWithTrainedAlgorithmicMedia`) loses it in every copy the proxy derives. `seo/services/images.py:86-88` saves WebP and AVIF without metadata. Google Merchant Center requires the tag on AI images.
  - Carry the source's XMP packet onto derived copies when it declares a digital source type (Pillow 13; confirm that its WebP and AVIF writers take `xmp=`).
  - Change the derived-file cache key, or copies cached before the fix stay untagged for a year.
  - The product graph's `ImageObject` (a CreativeWork; never the Product node) gets `digitalSourceType`.
- **No setting:** the mark is a duty, as it is for text.

**F1 as built (v0.177.0).**
- **Translations.**
  - `Translation.is_machine_translated` is the provenance: no second store. A store agent's write always sets it (`i18n.set_translation`, `i18n.translate_product`), whatever the model passes. An API token's write says what the caller says.
  - Changing the text in the translation editor clears it; the editor shows "Translated with AI" beside a published AI translation.
  - `core.i18n.services.overlay_translation` remembers which shown fields began as AI drafts (`ai_translated(obj)`).
  - ai_content marks them:
    - under a product's description, in the same `data-ai-generated` attribute as its own marks;
    - at `global_below_body` on any other page about one object;
    - in the graph, as one CreativeWork per field with `digitalSourceType`, which the main node points at through `subjectOf`.
  - The opt-in sentence has a translation wording, in Serbian and Croatian too.
- **Images.**
  - A copy carries a minimal XMP packet holding only the source's `DigitalSourceType`; the source's other metadata (creator, location) stays off the copies.
  - A tagged source's copies are cached as `….ai.<fmt>`, and `{% seo_responsive_image %}` addresses them with `?ai=1`.
  - The Product graph's image is an ImageObject with `digitalSourceType`.
- **Rulings:**
  - **Grid cards (lists of products, places, posts) carry no mark of their own;** the page each card links to carries it. Cost if wrong: a per-card mark, which C3 can add.
  - **The product carousel's thumbnails and the web stories keep their `/img/` addresses** (they build them outside seo). The server regenerates their copies with the tag, but a CDN copy cached before v0.177.0 may stay untagged until it expires.
  - **A product's own mark covers its own text only.** A field the page shows in a person's translation of AI-written text carries no mark; the person wrote that text (review of v0.177.0). Cost if wrong: one more mark on those pages.
  - **Art. 50(2) exempts output that does not substantially alter the input or its semantics,** and a translation may arguably fall under that. Marking follows the plan the owner accepted. Cost if wrong: a mark the law did not require.
- **Tests:** `core/i18n/tests/test_ai_translated.py`, `ai_content/tests/test_translation_marks.py`, `booking_marketplace/tests/test_translation_ai_marks.py` and `seo/tests/test_image_ai_tag.py` (a fixture image with the tag keeps it in WebP and AVIF; one without gets none).
- **help.md:** localization, ai_content, seo.
- **Live probe:** the read-only check in the probes list below.

**F2 · Claims and legal copy check (minor, M).**
- **Claims check.** seo's nightly site audit (`seo/services/site_audit.py`) reads product text, CMS pages and the rendered home, about and listing pages.
  - It looks for generic environmental claims and offset-based climate claims from a word list per language: English, Croatian, and Serbian in Latin and Cyrillic.
  - Each hit is a site-audit issue that names the page and the phrase, for the merchant to substantiate or remove.
  - It only reports, so it is on by default. Settings: an off switch and extra words.
  - Booking listings are Products (v0.109.0), so product text covers hosts' copy.
- **eco_impact's own copy** (the footprint badge, the tree add-on, the public totals page):
  - the footprint reads as an estimate and names its method;
  - no "climate neutral" or "carbon neutral" wording;
  - the add-on is described as a planting pledge, not as offsetting the order.
- **Legal-guarantee notice.** product_safety shows the harmonised legal-guarantee notice on goods pages (`pdp_below_long_description`; setting default off). This waits until the implementing regulation's text and layout have been read. If that text is not out, this part moves to the register.
- **Accessibility statement.** Compare gdpr's seeded accessibility page with the statement content the European Accessibility Act asks for (Directive 2019/882, Annex V). Fill the missing parts from store settings and the latest axe run; as every seed does, fill only empty fields.
- **Linda:** she reads the issues through the site audit's tools; check at execution and add them if missing.
- **Tests:** `seo/tests/test_claims_check.py` (each language, a hit per phrase, a clean page silent) and `eco_impact/tests/test_claims_copy.py`.
- **help.md:** seo, eco_impact, product_safety, gdpr.

**F2 as built (v0.178.0).**
- **Claims check** (`seo/services/green_claims.py`, read by `site_audit.collect`).
  - It reads the rendered visible text of every sitemap page (scripts and styles left out), plus each translated copy a page names in hreflang (at most 600 fetches, inside the audit's deadline). It does not query the database. Whatever a page shows is read: templates, app blocks, CMS pages and product text.
  - The text is folded before matching (case, accents, Serbian Cyrillic to Latin, `đ`, curly quotes, dashes), so one list covers English, Croatian and Serbian in both scripts. The list starts from the examples in recitals 9 and 12 of Directive 2024/825.
  - The audit has two findings:
    - `environmental_claim_offset` (warning): climate claims based on offsetting;
    - `environmental_claim_generic` (notice): generic claims.
  - Each finding names the page, the phrase and the words around it. A phrase on more than three pages is one line ("on 12 pages, e.g. /x/").
  - Settings: `seo.claims_check` (default on; it only reports) and `seo.claims_extra_words`. A merchant's own phrase matches in any script.
  - Linda reads the findings with `seo.audit_results`, whose description now names them.
- **eco_impact's copy.**
  - The badge reads "estimated footprint", with its method and a link to `/save-the-planet/#method`.
  - The add-on is a "tree-planting pledge" that "does not cancel out this order's footprint", and its order line is named so.
  - The public page lost its "kg CO2 offset" figure and the words "Save the planet". What the trees may absorb shows only on the dashboard, as an estimate.
  - The internal key `co2_offset_kg` and the `/save-the-planet/` address stay as they were.
- **Legal-guarantee notice** (product_safety).
  - Setting `legal_guarantee_notice`, default off. When on, every goods page (`sells_goods`) shows the Official Journal's colour artwork from Implementing Regulation (EU) 2025/1960, at 500 and 1000 px.
  - The artwork is shown whole, never folded away, and it links to the large copy. Its text follows in a fold for screen readers, with a link to Your Europe.
  - Linda reads whether a page shows it through `products.safety_info` (`shown.legal_guarantee_notice`), and switches it with `settings.set`.
- **Accessibility statement** (gdpr).
  - The seed now covers Annex V:
    - (a) the service;
    - (b) how it works;
    - (c) how it meets the requirements (EN 301 549 / WCAG 2.2 AA);
    - plus how it is checked, known limitations, contact and the authority.
  - It names the store's own name (never the "Morpheus Store" default), its contact email and its support phone (Art. 13(2): by voice too), with the date it was written. The phone is plain text, because cms's sanitiser keeps only http(s) and mailto links.
  - Migration `gdpr/0003` replaces a page that still holds either old seed text, whatever email it names. Both sides are compared as cms's sanitiser leaves them. A page the merchant changed is never touched.
- **Rulings:**
  - **The check reads rendered pages, not stored text.** A text no sitemap page shows is not read. Cost if wrong: a scan of product and CMS rows too.
  - **Bare "green", "eco" and "sustainable" are not in the list.** They match too much ("The Green Mile", "eco" as a prefix). A merchant adds them as extra words. Cost if wrong: claims written only with those words go unreported.
  - **Offset claims are warnings, generic claims notices.** A book about ecology is not a claim about the book, and the check cannot tell the two apart. Cost if wrong: a lower score for stores with real generic claims.
  - **The notice ships in English only.** The regulation publishes one per EU language, and the other files need downloading. Cost if wrong: a Croatian or Serbian store shows the English notice until its version ships.
  - **The accessibility statement has no setting for the authority or the limitations.** The seed writes the page once, so a later change to such a setting would change nothing (the settings-without-a-consumer landmine). The merchant edits the page in CMS. Cost if wrong: two settings and a re-seed.
  - **The migration writes live content on deploy**, the accessibility page of each store whose page is still the old seed. The merge is the yes for it.
- **Tests:**
  - `seo/tests/test_claims_check.py`: each language, once per page, offset before generic, extra words, the settings, the audit's findings, translated copies, switched off;
  - `eco_impact/tests/test_claims_copy.py`;
  - `product_safety/tests/test_legal_guarantee.py`;
  - `gdpr/tests/test_accessibility_statement.py`.
- **help.md:** seo, eco_impact, product_safety, gdpr.

**F3 · Online withdrawal function (minor, M; after A10a).**
- **Owners.** orders owns the record: a withdrawal is a notice on an order, and the returns record (`orders.ReturnRequest`) is reused if it fits (one concept, one owner). returns_portal owns the customer page, which C4 extends to returns and exchanges.
- **Where the link appears.** A link labelled "Withdraw from contract here" sits:
  - in the order email;
  - on the account order page;
  - on a public page linked from `footer_legal`.
- **Guests** identify the order by number and email:
  - the answer is the same whether or not they match;
  - lookups are rate-limited;
  - the form carries `{% bot_check "withdrawal" %}`, a new kind that the Cloudflare app answers.
- **The flow.** A form asks for the name, the order and where the acknowledgement goes. A second control, "Confirm withdrawal", submits it. An acknowledgement goes by email with the date and time of submission (a durable medium) and is stored with the record.
- **Lines with no right.** Lines whose right was waived (the digital-content waiver recorded at checkout) or that have none (a dated service) are listed with the reason, not offered.
- **What follows.** An unshipped order goes through A10a's cancel-with-refund. A shipped one becomes a return awaiting the goods: the staff flow today, with the customer side from C4.
- **Settings (returns_portal):** `withdrawal_function` (off | on, default off) and `withdrawal_days` (14, counted from delivery for goods; the merchant may lengthen it). The setup checklist and the nightly health check say when a store in an EU member state has it off.
- **Event:** `ORDER_WITHDRAWAL_REQUESTED`, wired at both ends (orders writes the timeline and fires it after commit; returns_portal sends the acknowledgement as its own email template and stamps it on the notice).
- **As built (v0.181.0).** Rulings made while building:
  - the acknowledgement is returns_portal's email template, not a core.emails key, so cms's template list needs no migration;
  - when no delivery date is known, goods count from dispatch plus 30 days;
  - the checklist and health check cover the EEA, not only EU member states;
  - an unshipped order with a line that may not be withdrawn becomes a return (cancelling part of an order is A10b);
  - the page's labels are translated (hr, sr); its error messages are not yet.
- **Linda:** `returns.list_withdrawals` (read) and `returns.process_withdrawal` (approval).
- **Translations:** labels in the hr and sr catalogues; Croatia transposed the article in June 2026.
- **Tests:**
  - `returns_portal/tests/test_withdrawal.py`: the two steps, the acknowledgement, guest lookup giving the same answer, lines without a right, the window;
  - the boundary trio;
  - `themes/test_withdrawal_link.py` (every theme).
- **help.md:** returns_portal, orders.

**F4 · Regional card gateway app (minor, M; owner's test credentials needed).**
- **The app.** A new opt-in app registers a `MonriGateway(PaymentGateway)` in `ready()`, as A9's `NetTermsGateway` is planned to. Monri is first because it lists Croatia, Serbia and Montenegro; read its current API documentation before the design.
- **Rules every gateway follows:**
  - offered only while switched on and configured;
  - callbacks verified by the acquirer's signature;
  - refunds through `RefundService`;
  - pre-authorisation for `capture_mode` where the acquirer offers it, else immediate capture;
  - the store or settlement currency the acquirer supports.
- **Payment page.** A new script or form origin goes into `PAYMENT_PAGE_SCRIPT_ORIGINS` and `docs/CHECKOUT_SCRIPTS.md` (PCI DSS 6.4.3) in the same change.
- **Live or test.** Read what the payments page and health checks already say. Add only a "live or test" line per card gateway, if missing.
- **Linda:** settings through `settings.set` (P7); refunds through `orders.refund`.
- **Tests:** the gateway contract (HTTP mocked), the signature check, refunds, and the gateway not offered while unconfigured.
- **help.md:** the new app and payments.

**F5 · Delivery estimate at checkout (patch, S).**
- **What shows.** When a rate has `estimated_days_min`/`max`, three places show them plus shipping's handling days as a business-day range:
  - the checkout's shipping choices;
  - the order page;
  - the placed email.
  When a rate has none, nothing shows.
- **Same numbers as the graph.** Read the same values as `shipping/seo_graph.py:_transit_days`, so the page and the structured data never disagree. The rate dict already carries them (`shipping/services.py:405`).
- **Setting:** `show_delivery_estimate` (shipping, default off).
- **Tests:** `themes/test_delivery_estimate.py` (every theme, both checkout forms) and a shipping unit test.
- **help.md:** shipping.

**F6 · Subscription cancel and pause by the customer (minor, S–M).**
- **The page.** `/account/subscriptions/` (subscriptions' storefront URLs; an account tile through `ACCOUNT_SUMMARY_FIELDS`) lists the customer's subscriptions. Today the storefront has only the membership and subscribe pages.
- **Cancel and pause** go through the services the merchant's actions use (Stripe Billing). The cancel is one labelled button and a confirmation, with no retention steps. Emails confirm both.
- **Settings:** `customer_cancel` (off | at period end | at once, default off) and `customer_pause` (off | on, default off).
- **Linda:** the existing subscriptions tools; any gap closes in this release.
- **Tests:** the boundary trio, cancel and pause through Stripe (mocked), the settings.
- **help.md:** subscriptions.

**F7 · Origin and HS code (minor, later).**
- `origin_country` and `hs_code` live as metafields owned by shipping, whose carrier labels (A4) fill customs forms from them.
- An import-charges notice shows at checkout for destinations outside the store's customs area (setting default off; the merchant's text). This is for a store outside the EU selling into it, where the EU's €3 duty per item has applied since 1 July 2026.
- No duty calculation: tax and duties engines are not done.

### Parked (decided, not scheduled)

Multi-store in one process (ADR 0018) — needs a tenant seam through settings, cache keys and media; passkeys (allauth login stages bypass `pre_login`); Amazon Seller / eBay / Etsy / TikTok Shop order sync; POS; accounting connectors; dashboard URL unification; LightGBM merchandising; SMS (no code exists; a provider app when a store asks).

## Verification

Per release: `ruff check . && ruff format --check .` (0.15.8); `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.<touched> plugins.installed.admin_dashboard.tests.test_disable_guards core.tests.test_settings_keys_have_readers`; `python manage.py check && makemigrations --check --dry-run`; the three boundary/standard scripts; `release --check`; Postgres rehearsal for every release with a migration (memory `releases-2026-10-22`); full serial suite before A1, A2, A6, B3, D2 and E6. After merge: watch all five stores to the new commit (`/readyz` ok + home 200), then the live probe named in each release (A1: a reduced-rate book's cart tax on dotbooks; A2: a scoped coupon on an out-of-scope cart refuses; B3: register + `me` over `/graphql/` with `enforce_csrf_checks`; D2: `/.well-known/ucp` lists capabilities and a checkout session round-trips on a staging token). Croatia is part of every deploy (owner, 2026-11-10): it builds from the same `main` and is in the smoke and accessibility checks. Phase F probes:
- F1: read-only, a `/sr/` or `/hr/` page shows `data-ai-generated` only where a published translation began as an AI draft. A tagged image's `/img/` copy carrying its XMP needs a tagged upload, so it needs the owner's yes; the suite covers it.
- F2: the next nightly audit lists claims issues, or none. Read-only: each store's `/p/accessibility/` shows the new statement unless its page was edited, and a goods page carries no `data-legal-guarantee` (the notice is off by default).
- F3: on a store that switches it on, with the owner's yes, a guest withdrawal round-trips and the acknowledgement email arrives.
- F4: one sandbox payment with the owner's test credentials.

## Sources

Read between 2026-11-06 and 2026-11-09. Vendor pages describe what each vendor ships; where a third-party article was the only source, the claim is marked as such in the matrix or left out.

**Medusa**
- Releases and changelog: https://github.com/medusajs/medusa/releases, https://medusajs.com/changelog/
- Commerce modules (Order, Promotion, Pricing, Inventory, Stock Location, Translation): https://docs.medusajs.com/resources/commerce-modules
- Order changes, edits, exchanges, claims: https://docs.medusajs.com/resources/commerce-modules/order
- Promotions, campaigns, budgets: https://docs.medusajs.com/resources/commerce-modules/promotion
- v2.18 pricing performance, inventory events: https://medusajs.com/blog/announcing-medusa-v2.18
- Newsletters (Jan, Apr, Aug 2026): https://medusajs.com/blog/newsletter-jan26/, https://medusajs.com/blog/newsletter-apr26, https://medusajs.com/blog/newsletter-aug-26
- Experimental translations: https://medusajs.com/blog/introducing-experimental-translations
- B2B starter: https://github.com/medusajs/b2b-starter, https://medusajs.com/b2b/
- MCP: https://medusajs.com/blog/announcing-medusa-mcp
- Agentic commerce tutorial: https://docs.medusajs.com/resources/how-to-tutorials/tutorials/agentic-commerce
- Integrations: https://medusajs.com/integrations/

**Saleor**
- Changelog: https://saleor.io/changelog, https://raw.githubusercontent.com/saleor/saleor/main/CHANGELOG.md
- 3.23 release (search vectors, gift card as payment, warehouse to channel stock): https://saleor.io/blog/3.23
- 3.22 upgrade guide (refund reasons, models): https://docs.saleor.io/upgrade-guides/core/3-21-to-3-22
- Promotions with predicates: https://docs.saleor.io/developer/discounts/promotions
- MCP: https://saleor.io/blog/saleor-mcp, https://docs.saleor.io/developer/ai
- ACP Instant Checkout app: https://saleor.io/blog/instant-checkout, https://saleor.io/cloud/agentic-commerce-protocol

**Shopify**
- Editions index: https://www.shopify.com/editions
- Winter '26: https://www.shopify.com/news/winter-26-edition-merchant
- Spring '26: https://www.shopify.com/news/spring-26-edition-dev
- Fall '26 (UCP default-on, agent profiles, knowledge base): https://www.shopify.com/news/fall-26-edition-merchant, https://www.shopify.com/news/fall-26-edition-developer
- Agents documentation (Catalog, Cart, Checkout, Order MCP): https://shopify.dev/docs/agents
- There is no official "Summer '26" edition; third-party pages using that name describe Spring '26.

**Agentic commerce protocols**
- Universal Commerce Protocol: https://ucp.dev, https://ucp.dev/latest/specification/overview/
- Agentic Commerce Protocol (OpenAI, Stripe): https://developers.openai.com/commerce/specs/checkout, https://developers.openai.com/commerce/specs/feed
- OpenAI scaling back Instant Checkout (March 2026): https://www.ecomcrew.com/openai-pulls-back-on-chatgpt-instant-checkout/, https://www.forrester.com/blogs/what-it-means-that-the-leader-in-agentic-commerce-just-pulled-back/embed/
- WebMCP: https://developer.chrome.com/docs/ai/webmcp
- Web Bot Auth: https://github.com/cloudflare/web-bot-auth
- Stripe Sessions 2026: https://stripe.com/blog/everything-we-announced-at-sessions-2026

**EU regulation 2026–2027**
- AI Act, Digital Omnibus: https://natlawreview.com/article/eu-digital-omnibus-ai-enters-force
- Code of practice on marking AI-generated content: https://digital-strategy.ec.europa.eu/en/news/commission-publishes-first-draft-code-practice-marking-and-labelling-ai-generated-content
- Cookie consent under the Digital Omnibus (proposal): https://www.heuking.de/en/news-events/newsletter-articles/detail/cookie-consent-under-the-digital-omnibus-planned-changes-and-technical-implementation.html
- Digital Product Passport timeline: https://www.renoon.com/blog/the-timeline-of-digital-product-passport-regulation-in-eu-espr-from-product-groups-to-rollout-schedule
- PSD3 and the Payment Services Regulation: https://www.mofo.com/pdf/resources/insights/260430-psd3-and-the-payment-services-regulation-key-developments
- VAT in the Digital Age milestones: https://www.vatupdate.com/2026/05/22/eu-commission-outlines-key-milestones-for-vida-e-invoicing-and-digital-reporting-implementation/
- European Accessibility Act enforcement: https://www.pinmeto.com/news/eu-accessibility-act-enforcement-french-courts-2026/
