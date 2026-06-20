# Marketing & Marketplace Apps — Analysis + Go-Forward (2026-06)

Analysis of the marketing/advertising-channel/marketplace plugins shipped this
cycle, against 2025-2026 market research, with a prioritized roadmap.
Research is dated mid-2026; treat vendor stats, ACP specifics, and geo/feature
availability as directional — re-verify primary docs at build time.

> ## ⚠ CORRECTION (post-write code audit) — agentic commerce is ALREADY BUILT
> The first draft below treated "make stores buyable by AI agents" (JSON-LD,
> feed for LLMs, llms.txt, shopping MCP, agentic checkout) as the headline *gap*.
> A code audit proved that wrong — Morpheus already ships, in `agent_mcp` + `seo`:
> - `/.well-known/ucp.json` — **Universal Commerce Protocol** manifest
>   (Google/Shopify/Stripe/Etsy/Walmart) declaring productSearch/cart/checkout.
> - `/.well-known/agent.json` — **Visa Trusted Agent + Mastercard Verifiable
>   Intent + Cloudflare Web Bot Auth**, with verified-agent order attribution.
> - **Live MCP shopping cluster**: `/mcp/storefront/v1/`, `/mcp/cart/v1/`,
>   `/mcp/checkout/v1/` (anonymous catalog reads → cart → checkout).
> - `seo`: `/llms.txt` + `/llms-full.txt`, per-PDP **`@type: Product` JSON-LD**
>   (`seo/services/meta.py`), and a **Schema.org Product feed for AI shopping
>   crawlers** with price/availability + an `agent_metadata` block
>   (`seo/services/ai_feeds.py`).
>
> **So Tier 1 below is ~90% done — Morpheus is at/ahead of the 2026 frontier on
> agentic discoverability.** The ONLY genuine agentic gap is the OpenAI/Stripe
> **ACP** checkout dialect (create/update/complete checkout session + delegated
> payment) — and UCP + MCP-checkout + Trusted-Agent already cover that
> *capability*, so ACP is a low-priority "speak one more protocol" item, not a
> differentiator to chase.
>
> **Revised priority: the real net-new value is the Tier 2 catch-up items**
> (cross-channel attribution, audience sync, email/SMS, ad automation) **and
> Tier 3 outbound marketplace sync** — NOT agentic discovery. Read Tier 2 as
> Tier 1. The #1 build is the **unified cross-channel attribution / blended ROAS
> dashboard** (item 4), which extends the `channels` plugin we already shipped.

---

## 1. What we have today (honest inventory)

**Strong: the channel-ads foundation.** Eight channel plugins — google_shopping,
meta_commerce, tiktok_commerce, pinterest_commerce, microsoft_commerce,
amazon_ads, reddit_ads, snapchat_commerce — plus a unified `channels` overview.
Per channel (varies): product **feed** (RSS/`g:` XML), **pixel/tag**,
**server-side Conversions API** (deduped), **ads reporting**, **campaign
list/pause/enable/create + budget**. This is genuinely competitive with
feed/channel tools (Feedonomics/Channable) + per-channel ad management. The
`channels` plugin already aggregates per-channel status + 30-day KPIs via the
`CHANNELS_OVERVIEW`/`CHANNELS_METRICS` hook filters.

**Supporting:** `tracking` (GA4/GTM + server-side + Consent Mode v2),
`analytics` (full-funnel, real-time, funnels), `marketing` (coupons +
EmailCampaign model + abandoned-cart event), `marketplace` (vendor onboarding,
order-splitting, commissions, payouts).

**Genuinely incomplete / stubbed:**
- `marketing` **email sending is stubbed** (model exists, no ESP/SMTP wired); no SMS; no automation/segmentation.
- `marketplace` is **inbound only** (vendors sell through our catalog) — **no outbound listing sync** to Amazon/eBay/TikTok Shop.
- microsoft_commerce ads is feed+UET only (SOAP API not built — deliberate).
- amazon_ads is ads-only (no Selling Partner listing/order sync).

---

## 2. What the market expects in 2026 (research)

- **Server-side CAPI + Consent Mode v2 is table-stakes**, not premium. 3rd-party
  cookies are dead in Safari/Firefox + unreliable in Chrome; Google deprecated
  all Privacy Sandbox APIs (Oct 2025). ✅ We largely have this per-channel + in `tracking`.
- **Platform-reported ROAS is no longer trusted** → merchants run blended **MER /
  multi-touch attribution / incrementality** (Triple Whale, Northbeam, Rockerbox).
  This is now baseline. ❌ **We have zero cross-channel attribution.**
- **Audience sync** (cart/customer/purchaser → Meta/TikTok/Pinterest custom +
  lookalike audiences) is standard. ❌ We fire pixels but sync no audiences.
- **Ad automation** — rules engines (Revealbot: condition→action, budget pacing,
  dayparting) AND the shift to "give a goal+budget+creative, the platform does
  the rest" (PMax / Advantage+ / TikTok Smart+). ❌ We have none.
- **Native email + SMS + segmentation** is now in-platform (Shopify bundles it). ◑ Stubbed.
- **Marketplace momentum: TikTok Shop** — US GMV ~$15B in 2025 (+68%); modern
  complete API. Meta/Instagram + Buy-on-Google **killed native checkout** (now
  feed/ad surfaces, not order-sync marketplaces).
- **★ Agentic commerce is the structural shift.** AI shopping agents (ChatGPT
  Instant Checkout, Perplexity Buy, Google AI-Mode "buy for me") now transact;
  the **Agentic Commerce Protocol (ACP)** (OpenAI+Stripe, Meta) is emerging.
  Merchants must expose: complete **JSON-LD/feed**, **real-time (~15-min)
  price/availability**, **ACP checkout-session + delegated-payment/auth +
  order webhooks**, and `llms.txt`. McKinsey projects ~$1T US agentic commerce by 2030.

---

## 3. The strategic read

Our **channel-ads layer is solid** and roughly at market parity for feeds +
per-channel ads. The table-stakes gaps (attribution, audience sync, automation,
email/SMS) are real but they're *catch-up* — chasing Shopify/Triple Whale on
their turf.

**The asymmetric opportunity is agentic commerce.** Morpheus already has the two
things Shopify is retrofitting via apps: a **first-class agent kernel** and an
**MCP cluster**. Making every Morpheus store natively *buyable by AI shopping
agents* (ACP endpoints + AI-discovery feed + shopping MCP) is where we can lead
rather than follow — and it compounds the "AI-first platform" thesis. This is
the highest-leverage direction.

---

## 4. Recommended roadmap (prioritized)

### Tier 1 — Lead: make stores buyable by AI agents (the differentiator)
1. **AI-discovery layer (`ai_discovery` plugin)** — auto-emit per-product
   **JSON-LD `Product`** (schema.org), a complete-GTIN normalized feed, and
   `/.well-known/llms.txt` / `llms.txt`; a **real-time price+availability
   endpoint** (≤15-min freshness). Low risk, pure addition, immediate "AI SEO" value.
2. **Shopping MCP surface** — extend the existing MCP cluster with a public,
   read-scoped "shopping" server (search catalog, get product, check
   availability) so external agents discover products. Reuses our MCP infra.
3. **Agentic checkout (ACP) endpoints** — create/update/complete checkout
   session + delegated payment (tokenized) + delegated auth (OAuth2) + order
   webhooks, mapped onto our cart/checkout/orders. *Bigger, ACP is beta — spike
   it behind a flag; verify the live spec.* This is the headline.

### Tier 2 — Close the ad table-stakes (extend what we built)
4. **Unified cross-channel attribution + blended ROAS dashboard** — extend the
   `channels` plugin: ingest each channel's spend (already in `CHANNELS_METRICS`)
   + our `analytics` order/revenue data → blended MER, per-channel
   contribution, last-/multi-touch models. Directly builds on the channels
   dashboard we shipped. **Highest-value catch-up item.**
5. **Audience sync** — sync cart-abandoners / customers / purchasers to Meta /
   TikTok / Pinterest / Snapchat custom + lookalike audiences (each channel
   plugin gains a `sync_audiences()` using its existing token). Reuses our CAPI plumbing.
6. **Finish email + SMS** — wire `marketing`'s EmailCampaign to an ESP (or core
   email) + an SMS provider; add trigger automations (abandoned-cart already
   fires the event) + basic segmentation. Table-stakes parity.
7. **Ad automation** — a rules engine (condition→action: "ROAS<2 → pause",
   "shift budget to top channel") + **Linda as AdOps operator** (goal+budget →
   she pings each channel's ads API, applies guardrails). Our single-Worker
   agent is the natural home; gate behind `enable_autonomous_operator` (already wired).

### Tier 3 — Outbound marketplace sync (new revenue surface)
8. **`MarketplaceChannel` abstraction** (separate from the inbound vendor
   plugin — one-concept-one-owner): central catalog → per-marketplace listing
   map → inventory buffer (anti-oversell) → order ingestion → fulfillment
   push-back, event-driven.
   - **TikTok Shop first** (momentum + modern API + content/AI fit),
   - then **Amazon SP-API** (largest volume, highest effort),
   - then **eBay** (cheapest to add once the abstraction exists).
   - Meta/Instagram + Google: **feed exporters, not order-sync** (native checkout dead) — extend existing channel feeds.

### Tier 4 — Creative + predictive (AI depth)
9. **Catalog-to-creative generator** — Linda generates ad copy + image/short-video
   variants from a product, brand-safe templating; feeds the channel ad APIs.
10. **Predictive layer** — churn/LTV scoring + spend-anomaly detection wired to
    agent auto-actions (not just dashboards).

---

## 5. Suggested sequence

Start **Tier 1.1 (AI-discovery layer)** — small, pure-additive, immediately
useful, and it stakes the agentic-commerce ground. Then **Tier 2.4 (unified
attribution dashboard)** — the highest-value catch-up, and it extends the
`channels` plugin we already shipped. Tier 1.3 (ACP checkout) is the headline
but is the biggest/most-uncertain (beta spec) — spike it deliberately. Each is
its own plugin/PR following the channel-plugin pattern; none requires touching core.

## Sources
Shopify Editions Winter '26; Triple Whale/Northbeam/Rockerbox attribution
comparisons; Feedonomics/DataFeedWatch/Channable; Revealbot; Amazon SP-API /
Walmart / eBay / Etsy / TikTok Shop dev docs; Shopify Marketplace Connect;
Momentum Works TikTok Shop GMV; Stripe ACP docs + agentic-commerce-protocol spec;
OpenAI Instant Checkout; Google/Meta checkout sunset notices. (Full URLs in the
research briefs that produced this doc; re-verify before implementation.)
