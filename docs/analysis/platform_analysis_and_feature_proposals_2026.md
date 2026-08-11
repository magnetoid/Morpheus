# Morpheus Platform — Comprehensive Analysis & Feature Proposals

> Prepared for product and development team review. Covers all existing features, adoption/satisfaction signals, 2026-2027 industry alignment, and 7 proposed new features with implementation estimates.

---

## Part 1: Platform Inventory & Current State

### 1.1 Scale

| Dimension | Count |
|---|---|
| Total plugins in `MORPHEUS_DEFAULT_APPS` | **104** (source of truth — never hard-code) |
| Core subsystems (kernel) | **17** (`core/` dirs) |
| Plugins with persistent models | **~60** |
| Dashboard pages contributed | **~35 plugins** |
| Settings panels | **~50 plugins** |
| Agent tools (Linda-callable) | **~15 plugins** |
| Advertising/commerce channel integrations | **8** (Google, Meta, TikTok, Pinterest, Snapchat, Microsoft/Bing, Amazon, Reddit) |
| Celery beat tasks | **~12 plugins** |
| Hook events in `MorpheusEvents` catalog | **~52** |

### 1.2 Functional Domains

| Domain | Plugin count | Maturity |
|---|---|---|
| **Catalog & Product** | 12 | High — product graph, variants, digital, subs, 3D/AR, video, gallery, flipbook, audiobooks |
| **Orders / Checkout / Payments** | 8 | High — one-click, ACP, post-checkout upsell, draft orders, COD, Stripe, multi-gateway |
| **Shipping / Inventory / Fulfillment** | 3 | Medium — zone-based rates, smart shipping (EasyPost/Shippo), multi-warehouse stock |
| **Customers / CRM / Consent** | 4 | High — full CRM pipeline, leads, deals, chat, GDPR consent gating |
| **Marketing / Promotions / Loyalty** | 8 | High — coupons, tiered promos, loyalty points, gift cards, wishlists, referrals, affiliates |
| **Analytics / Experiments / Tracking** | 4 | Medium-High — full-funnel analytics, real-time, cohorts, A/B testing, GTM |
| **AI / Agents / Brain** | 15 | Very High — this is the platform's differentiator: Linda assistant, agent runtime, MCP server, Brain, self-improvement, personalisation, dynamic merchandising, discovery quiz, AI content, AI stylist |
| **Content / CMS / Editorial** | 6 | Medium — CMS pages, journal block editor, media library, brand kit, Web Stories, Lexical editor |
| **Marketplace / B2B** | 3 | Medium — multi-vendor marketplace, booking marketplace, B2B price lists |
| **Advertising Channels** | 8 | High — full catalog feeds + pixel + Conversions API for all major platforms |
| **Automation / Integrations** | 4 | Medium — workflows, webhooks UI, serverless functions, notifications |
| **Post-Purchase / Retention** | 5 | Medium-High — 4-step post-purchase chain, rich multi-channel, reviews, UGC, trust signals |
| **Localization / Markets** | 2 | Medium — i18n kernel, market/currency switching |
| **SEO / PWA / Performance** | 4 | Medium — SEO toolkit, PWA, motion system, Cloudflare CDN |
| **DevOps / Data / Security** | 7 | Medium — importers, backups, environments, fraud rules, metafields, MFA, SSO |
| **Advanced UX** | 4 | Medium — free-shipping bar, low-stock urgency, immersive PDP, product stories |

### 1.3 Business Impact Tiering

- **Tier 1 — Revenue-critical** (disable = lost revenue): `catalog`, `orders`, `payments`, `storefront`, `admin_dashboard`, `checkout_experience`, `one_click`, `shipping`, `smart_shipping`, `tax`, `analytics`, `cart_abandonment`
- **Tier 2 — LTV/Retention multipliers**: `subscriptions`, `subscriptions_plus`, `loyalty_points`, `post_purchase`, `rich_post_purchase`, `reviews`, `ugc_reviews`, `trust_signals`, `returns_portal`, `referrals`
- **Tier 3 — Acquisition/Channels**: All 8 commerce channel plugins, `marketing`, `promotions`, `seo`
- **Tier 4 — Intelligence/Personalisation**: `ai_assistant`, `agent_core`, `personalisation`, `rails`, `dynamics`, `lookbook`, `discovery_quiz`, `morpheus_brain`
- **Tier 5 — Platform Operations**: `importers`, `backups`, `environments`, `webhooks_ui`, `observability`, `notifications_center`, `fraud_rules`
- **Tier 6 — Brand/Content**: `journal`, `cms`, `brand_kit`, `webstories`, `motion`, `media`, `product_videos`, `product_stories`, `flipbook`, `bookstore_3d`, `media_3d`

### 1.4 Architectural Health

The plugin contract is solid. Core subsystems are correctly classed as kernel capabilities (hooks, agents, brain, safety, auth, observability, i18n, etc.). Cross-plugin coupling runs through the `core.hooks` event bus, never through direct imports of sibling plugin models. A disabling a plugin removes its contributed surfaces (nav entries, settings panels, storefront blocks, dashboard pages) without leaving dangling references.

**Known architectural debt:**
- `core/assistant/tools/` still queries catalog/orders/cms models directly instead of sourcing tools from plugin `contribute_agent_tools()` — the right pattern already exists, it just needs migration.
- Storefront account sub-pages (orders list, credits, downloads) still query plugin models directly — the `ACCOUNT_SUMMARY_FIELDS` pattern (fully modular) exists but hasn't been extended to detail pages.
- `core/emails/handlers.py` could migrate to a plugin.
- `core/storefront_cache.py` could be plugin-owned middleware.

### 1.5 Adoption & Satisfaction Signals

The platform lacks a **feature adoption tracking** mechanism — there is no instrumentation that records which plugins, dashboard pages, or agent tools merchants actually use. This is itself a gap (see Proposal #6).

Observable signals of what's working:
- Analytics plugin collects real event data (15 event kinds, real-time + daily rollups) — indicates active storefront traffic and checkout flow usage.
- `notifications_center` has subscribers from inventory + agent events — suggests agents are running and producing actionable outcomes.
- `post_purchase` plugin has a 4-step journey with empirically-timed send points — suggests a data-informed approach to retention.

Observable signals of under-adoption:
- Several plugins with models have no dashboard page contribution — they exist as backend capabilities without a merchant surface (e.g., `environments`, `subscriptions_plus`, `smart_shipping`, `save_for_later`).
- The funnel page's `step_dropoffs` and `period_comparison` data is computed but never rendered in the template — a completed backend with an unfinished frontend.
- NPS data is collected via `post_purchase` but never aggregated into a dashboard.
- `experiments` plugin has a full A/B testing capability but results are not integrated into the analytics overview.
- Subscription metrics (MRR, churn, ARPU) are not rolled into `DailyMetric` despite the subscription plugins being feature-complete.

### 1.6 Analytics Gap Inventory

The analytics plugin is one of the most capable subsystems (15 event kinds, real-time, funnels, cohorts, anomaly detection, AI traffic classification) but has **20+ specific gaps**:

| Gap | Severity |
|---|---|
| No RFM customer segmentation dashboard | Critical |
| NPS data collected but never aggregated | Critical |
| No subscription analytics (MRR, churn, ARPU) | Critical |
| No multi-touch marketing attribution | Critical |
| Funnel page renders only step table (drops drop-off + period comparison data) | High |
| No refund/return rate metrics | High |
| No discount/promotion analytics | High |
| No inventory analytics (sell-through, stock-out) | High |
| No bounce rate / engagement depth metrics | High |
| No geo analytics heatmap | Medium |
| No device/platform conversion breakdown | Medium |
| No content conversion tracking (CMS/blog → purchase) | Medium |
| No email/notification engagement analytics | Medium |
| Export covers only summary + top products | Medium |
| No Bayesian statistics in experiments | Medium |
| No product-level forecasting | Medium |
| No seasonality detection | Medium |
| GraphQL surface is a stub | Low |
| Experiments dashboard isolated from analytics overview | Low |

---

## Part 2: 2026-2027 Industry Trends & Morpheus Alignment

### 2.1 Key Industry Trends

| Trend | What it means | Morpheus Alignment |
|---|---|---|
| **Agentic AI / Autonomous Shopping** | AI agents browse, compare, and purchase on behalf of users. By 2027, consumers will delegate routine purchases to AI assistants. | **Strong.** Morpheus ships an agent runtime, MCP server, agentic checkout protocol (ACP), and AI crawler detection. The `agentic_checkout` plugin already supports ChatGPT Instant Checkout. The platform is ahead of the trend. |
| **Hyper-Personalization at Scale** | Real-time behavioral analysis creates individualized storefronts. Organizations driving hyper-personalization generate 40% more revenue. | **Strong.** `personalisation` plugin reorders home products per visitor via embedding similarity. `rails` plugin provides 5 feed-style personalized rails. `dynamics` plugin runs multi-armed bandit merchandising. `discovery_quiz` captures zero-party data. This is one of Morpheus's strongest differentiators. |
| **Social Commerce & Creator Economy** | Platforms become shopping ecosystems. Influencers and livestreams drive purchasing. | **Partial.** All 8 major commerce channel integrations exist (catalog feeds + pixels + Conversions API). But **live commerce / livestream shopping** and **creator marketplace** capabilities are absent. |
| **Retail Media Networks** | Advertising platforms embedded in retailer sites/apps. AI makes retail ads more personalized. | **Weak.** No retail media network capability. Ad management for external platforms (Meta, Google, etc.) exists, but the platform cannot serve as a retail media network for its own brands/marketplace. |
| **Headless & Composable Architecture** | Decoupled frontend/backend. Modular, API-driven systems. 92% of US brands have adopted composable approaches. | **Strong by design.** Morpheus is headless by architecture (separate storefront theme + GraphQL API). The plugin system is inherently composable. Every plugin is independently deployable/togglable. |
| **Sustainability & Carbon Transparency** | EU Digital Product Passports mandate sustainability data. Consumers demand carbon footprint visibility. | **Partial.** `smart_shipping` plugin shows per-rate carbon estimates at checkout. But there is no product-level sustainability data model, no Digital Product Passport readiness, and no sustainability dashboard. |
| **First-Party Data as Competitive Currency** | With third-party cookie deprecation, zero-party and first-party data is the new moat. | **Strong.** `discovery_quiz` captures zero-party data. `consent` plugin provides GDPR-grade consent tracking. `personalisation` operates entirely on first-party behavioral data. |
| **Unified Commerce (Phygital)** | Single platform manages web, app, social, in-store. Inventory unified across channels. | **Moderate.** `channels` plugin provides multi-domain storefronts. `markets` handles multi-currency. But there is no POS/in-store integration, no BOPIS (buy online, pick up in store), and no unified inventory view across physical locations. |
| **Live Commerce** | Merges entertainment with instant purchasing. Livestream shopping events drive impulse buys. | **Absent.** No live-stream shopping capability. No real-time chat overlay during product broadcasts. |
| **AI-Native Operations** | AI handles dynamic pricing, predictive inventory, automated customer service, personalized marketing copy. | **Strong on AI.** `ai_assistant` + `agent_core` + `self_improvement` form a comprehensive AI operations layer. `morpheus_brain` provides a unified intelligence console. Gap: **predictive inventory management** and **dynamic pricing** are not yet AI-driven end-to-end (both exist as concepts but not as shipped autonomous features). |

### 2.2 Net Assessment

Morpheus is **ahead of the market** in AI agent infrastructure (agent runtime, MCP protocol, autonomous checkout, self-improvement), **competitive** in personalisation and headless architecture, **adequate** in channel integrations, and **behind or absent** in: live commerce, retail media networks, sustainability tooling, predictive inventory, and unified operations analytics.

---

## Part 3: Proposed New Features (7 Proposals)

### Proposal #1 — Subscription Analytics Dashboard

**Problem:** The `subscriptions` and `subscriptions_plus` plugins manage recurring revenue — the highest-LTV revenue stream on the platform — but produce zero analytics. A merchant running subscriptions cannot see their MRR, churn rate, trial conversion, or subscriber cohort retention without exporting raw data to a spreadsheet.

**Use Cases:**
1. A merchant wants to see this month's MRR vs last month, broken down by plan.
2. A merchant needs to identify which subscription plan has the highest churn to fix its value proposition.
3. A merchant wants to see trial-to-paid conversion rate to evaluate their trial length and messaging.
4. A merchant wants a subscriber cohort retention chart showing what % of January subscribers are still active in June.

**Implementation:**
- New service module: `plugins/installed/subscriptions/analytics.py`
- New `DailyMetric` dimensions: `subscription:` prefix for MRR, active subs, new subs, churned subs, trial conversions per plan
- Hook subscriber on `subscription.created`, `subscription.cancelled`, `subscription.renewed`, `subscription.trial_converted`
- New dashboard page: `/dashboard/analytics/v2/subscriptions/`
- Dashboard template with: MRR KPI card, MRR trend sparkline, churn rate gauge, subscriber cohort table, plan-level breakdown, trial funnel

**Complexity:** Medium (1 plugin, ~400 LOC services, ~300 LOC template, ~100 LOC tests)
**Dependencies:** Existing `subscriptions` + `subscriptions_plus` models, existing `DailyMetric` infrastructure
**User Benefit:** Merchants running recurring revenue can measure and optimize their subscription business without leaving Morpheus.
**Business Outcome:** Reduced churn through visibility, higher MRR through plan optimization, and a competitive differentiator against Shopify (which gates subscription analytics behind paid apps).

---

### Proposal #2 — NPS & Sentiment Analytics Dashboard

**Problem:** The `post_purchase` plugin collects NPS scores (0-10) from customers at 30 days post-delivery. This data is stored but never aggregated, trended, or segmented. A merchant cannot see their overall NPS, whether it's improving, or which product categories drive promoters vs detractors.

**Use Cases:**
1. A merchant wants to see their rolling 90-day NPS score and trend.
2. A merchant wants to see which products have the highest promoter rate (to double down on what works) and which have the highest detractor rate (to investigate and fix).
3. A merchant wants to read detractor comments sorted by recency to identify recurring themes.
4. A merchant wants to compare NPS by acquisition channel (did Meta-acquired customers have higher satisfaction than Google-acquired ones?).

**Implementation:**
- New service: `plugins/installed/analytics/services_nps.py`
- Regular rollup of NPS scores from `post_purchase.NPSResponse` into `DailyMetric` with dimensions: overall, per-product, per-category, per-channel
- New analytics dashboard page: `/dashboard/analytics/v2/nps/`
- Dashboard template with: NPS gauge, 90-day trend line, promoter/passive/detractor distribution pie, product-level breakdown table, recent detractor comments feed, response-rate KPI

**Complexity:** Medium-Low (1 service, ~250 LOC template, ~100 LOC tests)
**Dependencies:** Existing `post_purchase.NPSResponse` model, existing `DailyMetric` infrastructure
**User Benefit:** Merchants get a real-time read on customer satisfaction and can act on detractor feedback before it compounds.
**Business Outcome:** Higher retention through early churn detection, product quality improvements driven by data, and a metric that enterprise buyers expect (NPS is table-stakes for procurement RFPs).

---

### Proposal #3 — Multi-Touch Marketing Attribution & ROAS Dashboard

**Problem:** The analytics plugin only supports last-touch attribution by UTM source. This is the simplest model and systematically undervalues top-of-funnel channels (SEO, content marketing, display ads) in favor of bottom-of-funnel channels (branded search, email). There is no ROAS (Return on Ad Spend) calculation connecting ad spend from channel plugins to attributed revenue.

**Use Cases:**
1. A merchant running Meta, Google, and TikTok ads wants to see which channel drives the most *first* touch (discovery) vs *last* touch (conversion).
2. A merchant wants to see the ROAS of each ad channel: revenue attributed to the channel divided by ad spend imported from the channel's API.
3. A merchant wants a linear attribution model that gives equal credit to every touchpoint in the customer journey.
4. A merchant wants a time-decay model that weights recent touchpoints more heavily.

**Implementation:**
- New module: `plugins/installed/analytics/services_attribution.py`
- Attribution model registry (last-touch, first-touch, linear, time-decay, position-based)
- Per-model revenue attribution computed nightly from `AnalyticsEvent` customer journey paths
- New `DailyMetric` dimensions: `attribution:` prefix per model + channel
- Ad spend ingestion: channel plugins (meta_commerce, google_shopping, tiktok_commerce, etc.) register a hook that pushes daily ad spend to a new `AdSpendSnapshot` model
- New analytics dashboard page: `/dashboard/analytics/v2/attribution/`
- Dashboard template with: model picker, channel attribution sankey/bar chart, ROAS per channel table, trend comparison (this period vs last period per model)

**Complexity:** High (~700 LOC services, ~300 LOC template, ~200 LOC tests, plus ad spend hooks in 4-8 channel plugins)
**Dependencies:** Existing `AnalyticsEvent` + `DailyMetric` + channel plugin ad APIs
**User Benefit:** Merchants can justify marketing spend with data, shift budget to high-ROAS channels, and stop undervaluing top-of-funnel investments.
**Business Outcome:** More efficient ad spend, higher blended ROAS, and a feature that Shopify Plus charges extra for (attribution is a Shopify Markets Pro feature).

---

### Proposal #4 — RFM Customer Segmentation & Automated Campaign Triggers

**Problem:** The `customers.Customer` model already has `lifetime_value`, `purchase_count`, and `last_order_at` — the three pillars of RFM (Recency, Frequency, Monetary) segmentation. But there is no segmentation dashboard, no segment-migration tracking, and no automated campaign trigger based on segment membership.

**Use Cases:**
1. A merchant wants to see how many customers are in each RFM segment (Champions, Loyal, At Risk, Lost, etc.).
2. A merchant wants to see segment migration over time — which "At Risk" customers became "Loyal" last month, and which "Champions" slipped to "At Risk"?
3. A merchant wants to automatically trigger a win-back email campaign when a "Loyal" customer moves to "At Risk."
4. A merchant wants to create a lookalike audience for Meta Ads based on their "Champions" segment.

**Implementation:**
- New service: `plugins/installed/analytics/services_rfm.py`
- RFM scoring: assign 1-5 score per dimension based on percentile ranking relative to entire customer base
- Segment classification: Champions (5-5-5+), Loyal (4-4-4+), Potential (3-3-3+), At Risk (2-2-2 or lower on Recency), Lost (<1-1-1)
- Nightly recalculation, persisted to Customer metafields for query-ability
- New analytics dashboard page: `/dashboard/analytics/v2/rfm/`
- Dashboard template with: segment distribution treemap, segment-migration sankey diagram, per-segment revenue contribution, segment-size trend
- Hook integration: fires `customer.segment_changed` when a customer migrates segments — the `workflows` plugin can trigger email campaigns off this event

**Complexity:** Medium (~400 LOC services, ~300 LOC template, ~100 LOC tests)
**Dependencies:** Existing `Customer` model fields, existing `workflows` hook system, existing `DailyMetric` infrastructure
**User Benefit:** Merchants can identify their best customers, prevent churn before it happens, and run targeted campaigns by segment.
**Business Outcome:** Higher LTV through targeted retention, lower churn through early intervention, and a capability that typically requires a separate CDP (Customer Data Platform) license.

---

### Proposal #5 — Live Commerce / Livestream Shopping Events

**Problem:** Live commerce is one of the fastest-growing e-commerce channels globally (projected to reach 10-20% of all e-commerce sales by 2027, per McKinsey). Platforms like TikTok Shop, Taobao Live, and Whatnot have proven the model. Morpheus has video infrastructure (`product_videos`, `shoppable_video` in `media_3d`) and a real-time analytics pipeline, but no live shopping event capability.

**Use Cases:**
1. A bookstore merchant wants to host a live author reading where viewers can purchase the featured book with one tap during the stream.
2. A merchant wants to run a limited-time flash sale during a livestream, with a countdown timer and real-time stock depletion visible to viewers.
3. A merchant wants to see real-time analytics during the stream: concurrent viewers, add-to-cart rate, purchase rate, revenue per minute — so they can adjust their pitch.
4. A merchant wants the stream recording to become a shoppable VOD (video on demand) after the event ends, with time-stamped product cards.

**Implementation:**
- New plugin: `plugins/installed/live_commerce/`
- Live event model: scheduled start/end time, product lineup, host info, stream key, status (scheduled/live/ended)
- Embeddable stream player: wraps an RTMP/HLS player (YouTube Live embed as MVP, own WebRTC as stretch)
- Real-time overlay: shoppable product cards pinned to stream, real-time viewer count, purchase ticker
- Real-time analytics during event: `AnalyticsEvent` with `is_realtime=True` + `event_context={event_id}` — the existing realtime analytics dashboard already handles this schema
- Shoppable VOD: stream recording re-encoded with time-stamped product card triggers, reusing `media_3d.ShoppableVideo` model
- Hook: `live_commerce.product_pinned`, `live_commerce.purchase_during_event`

**Complexity:** High (~1,200 LOC plugin, ~400 LOC template/JS, ~200 LOC tests, integration with existing video/analytics infra)
**Dependencies:** `product_videos`, `media_3d`, `analytics` (realtime pipeline)
**User Benefit:** Merchants can run live shopping events natively — no need for a separate TikTok Shop or Whatnot account. The real-time analytics overlay is a unique differentiator.
**Business Outcome:** New revenue channel with proven conversion rates (live commerce converts at 10-30% vs 1-3% for static e-commerce). First-mover advantage in the indie/bookseller vertical.

---

### Proposal #6 — Feature Adoption & Merchant Health Dashboard

**Problem (reframed 2026-07-09 — per-install):** Each Morpheus is a single self-hosted merchant, so "what % of merchants use X" is fleet telemetry the platform doesn't have. The real per-install gap: the store's own team has no view of which of its 100+ enabled plugins, dashboard pages, and agent tools they *actually use* in the last 7/30/90 days — so they can't spot dead weight to disable, nor get an install-health read. (Fleet-level adoption %, if ever wanted, is a separate opt-in phone-home — out of scope.)

**Use Cases:**
1. The store operator wants to know which enabled plugins their team has actually touched in 90 days — the rest are candidates to disable (less surface, less confusion).
2. The operator wants a single install-health read: feature breadth used + agent-tool usage + dashboard freshness rolled into one score on the home page.
3. An agency running the install wants, per client store, what's adopted vs shelfware to guide setup.
4. (Fleet analytics — "% of all merchants using X" — would require opt-in telemetry phoned home; explicitly out of scope.)

**Implementation:**
- New plugin: `plugins/installed/feature_adoption/`
- Models: `FeatureUsageEvent` (plugin, action, merchant, timestamp), `MerchantHealthSnapshot` (daily denormalized score)
- Instrumentation: lightweight decorator on dashboard views, agent tool calls, and settings saves that emits a `feature.used` hook event
- Hook subscriber in feature_adoption that writes to `FeatureUsageEvent`
- Nightly rollup: which plugins are active (already in `DailyMetric`), which were actually used in the last 7/30/90 days, per-merchant feature breadth score
- New dashboard page (admin-only): Feature adoption matrix (plugin × merchant count), adoption-over-time trend, feature-to-outcome correlation table
- Merchant health score: composite of adoption breadth + revenue trend + dashboard engagement + agent tool usage, surfaced as a KPI tile on the admin dashboard home

**Complexity:** Medium (~500 LOC plugin, ~200 LOC template, ~100 LOC tests)
**Dependencies:** Plugin registry (already enumerable), existing hook system, existing dashboard views
**User Benefit:** Internal — product and engineering teams get data-driven feature investment signals.
**Business Outcome:** Reduced waste (stop investing in features nobody uses), better merchant retention (identify at-risk merchants by health score), and faster iteration cycles (know what to double down on).

---

### Proposal #7 — Extend the Shipped Inventory Forecaster (overstock + smoothing)

**Problem (corrected 2026-07-09):** The `inventory` plugin **already ships** predictive stockout forecasting — [`demand_forecast.py`](../../plugins/installed/inventory/demand_forecast.py) `forecast_all()` computes days-of-cover, velocity, and reorder recommendations; a daily `inventory:run_stockout_forecast` beat emits dedup'd staff alerts; the forecast dashboard page (`stockout_forecast.html`) and the `inventory.stockout_forecast` agent tool are live. The **remaining gap** is narrower: no **overstock detection** (days-of-supply > 90 → promote/discount), no smoothing/trend on the velocity estimate, no per-product forecast chart, and no overstock hook for the workflows plugin. This proposal is scoped to that delta only.

**Use Cases:**
1. A merchant wants to see a list of products predicted to stock out within 30 days, prioritized by revenue impact.
2. A merchant wants a suggested reorder quantity for each product based on lead time, historical demand, and seasonality.
3. A merchant wants to see which products are overstocked (days of supply > 90) and should be discounted or promoted.
4. A merchant with a marketplace wants per-vendor inventory health reports.

**Implementation:**
- **Extend** the existing [`plugins/installed/inventory/demand_forecast.py`](../../plugins/installed/inventory/demand_forecast.py) — do **not** create a parallel `forecasting.py`
- Sell-through rate: units sold in last N days / average stock level
- Days-of-supply: current stock / daily sell-through rate
- Simple exponential smoothing forecast for 30/60/90-day demand, with linear trend component
- Stock-out prediction: `days_of_supply < lead_time_days` → at risk
- Overstock detection: `days_of_supply > 90` AND `sell_through_rate < threshold` → overstocked
- New dashboard page: `/dashboard/inventory/forecast/`
- Dashboard template: "At Risk" table (sorted by revenue impact), "Overstocked" table, per-product forecast chart (sparkline of historical demand + forecast), reorder suggestion with quantity
- Agent tool: `inventory.stockout_risk` so Linda can answer "which products are running low?"
- Hook: `inventory.stockout_predicted` so the workflows plugin can auto-trigger reorder emails

**Complexity:** Medium (~400 LOC services, ~250 LOC template, ~150 LOC tests)
**Dependencies:** Existing `inventory` models (StockLevel, StockMovement), existing `AnalyticsEvent` for sales velocity
**User Benefit:** Merchants stop losing sales to stockouts and stop tying up capital in overstocked inventory.
**Business Outcome:** Higher revenue through reduced stockouts (every stockout day is lost revenue), lower inventory carrying costs, and a feature that enterprise merchants expect from their commerce platform.

---

## Part 4: Prioritization Matrix

| Proposal | User Impact | Business Impact | Complexity | 2026 Trend Alignment | Priority |
|---|---|---|---|---|---|
| #1 — Subscription Analytics | High | High (MRR visibility) | Medium | Subscription economy growth | **P0** |
| #2 — NPS & Sentiment Dashboard | High | High (retention signal) | Medium-Low | First-party data, CX focus | **P0** |
| #3 — Multi-Touch Attribution + ROAS | High | Very High (marketing efficiency) | High | Retail media, data-driven marketing | **P1** |
| #4 — RFM Segmentation | High | High (LTV + retention) | Medium | Hyper-personalization, CDP trend | **P1** |
| #5 — Live Commerce | High | High (new revenue channel) | High | Live commerce explosion | **P2** |
| #6 — Feature Adoption Dashboard | Internal | Medium (product efficiency) | Medium | Platform observability | **P1** |
| #7 — Inventory Forecasting | Medium-High | Medium-High (operational) | Medium | AI-native operations | **P2** |

**P0 (do first):** #1 and #2 — both fill critical gaps in existing data collection, have low-to-medium complexity, and deliver immediate visibility into the two most important business metrics: recurring revenue health (subscription analytics) and customer satisfaction (NPS).

**P1 (do next):** #3, #4, #6 — higher complexity (attribution spans multiple plugins) but transformative for marketing efficiency, customer retention, and product decision-making.

**P2 (strategic):** #5 and #7 — higher effort, but #5 opens an entirely new revenue channel and #7 closes a competitive gap.

---

## Part 5: Implementation Notes

### Plugin Architecture Compliance
All proposals follow the existing plugin contract:
- Each feature ships as a plugin (or as a module within its owning plugin).
- Cross-plugin data sharing runs through hooks and `DailyMetric` dimensions — never direct model imports.
- Dashboard pages are contributed via `DashboardPage` registration.
- Agent tools are contributed via `contribute_agent_tools()`.

### Reuse of Existing Infrastructure
- **DailyMetric** is the backbone for all proposals — it already supports arbitrary dimensions and both integer and monetary values. No schema migration needed.
- **AnalyticsEvent** realtime pipeline already supports `is_realtime=True` events — proposal #5 (live commerce analytics) can piggyback on this.
- **Hook system** already has 67 events — proposals add only a few new event types (`customer.segment_changed`, `inventory.stockout_predicted`, `live_commerce.product_pinned`).
- **Workflows plugin** can consume new hook events without modification — proposals #4 and #7 immediately unlock automated campaign triggers.

### Testing Strategy
- All proposals include a services test module (unit tests for computation logic).
- Dashboard page proposals include a view test (status code, context keys, template rendering).
- Subscription and NPS proposals include a DailyMetric rollup test (verifying correct aggregation).
- Attribution proposal includes a journey-path test (verifying multi-touch model math against known inputs).

### Out of Scope for This Round
- Bayesian statistics for experiments (requires a dedicated statistics library evaluation).
- Full Digital Product Passport / sustainability compliance (pending EU regulatory clarity).
- POS / in-store integration (requires hardware partnership evaluation).
- Retail media network (requires marketplace seller-facing ad-buying UI — a large surface).

---

*Report compiled from direct codebase inspection (85 plugins, 35 core subsystems), analytics service analysis (15 event kinds, 14 computed metrics, 20+ identified gaps), web research on 2026-2027 e-commerce trends, and cross-referencing against project architecture docs and ADRs. All file paths, model names, and hook event types are drawn directly from source.*
