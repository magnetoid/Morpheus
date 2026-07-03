# Morpheus OS → cutting-edge open-core commerce: market research + master plan

**Date:** 2026-07-03 · **Method:** 26-agent workflow — 7 web-research angles
(2025–26 sources), 6 codebase audits, 10 critical claims adversarially
fact-checked, 3 pillar syntheses. Raw corpus in the session workflow output;
this doc is the distilled, sequenced plan.

## The positioning insight

The verified market gap Morpheus can own: **developer-first OSS commerce
(Medusa/Saleor/Vendure) ships no batteries-included merchant admin, while the
batteries-included incumbent (WooCommerce) is shrinking (-11% live stores
YoY).** Nobody in open source offers: a Shopify-grade merchant admin + a real
staff AI operator + agent-native surfaces. That is Morpheus's lane:
**"the open-source AI-operated storefront — Shopify polish, your own
infrastructure, an operator (Linda) built in."**

## Ten verified market findings (mid-2026)

1. **The great reversal** *(confirmed)* — In-chat checkout lost. OpenAI
   Instant Checkout (Sept 2025) retreated by March 2026 (~30 merchants live,
   ~3× worse conversion than click-through per Walmart; only 22% of shoppers
   ever completed a purchase inside an AI tool). Winning posture: **discovery
   in AI, checkout on the merchant's own storefront** — agent-legible feeds +
   manifests + prefilled-cart handoff. ChatGPT drove ~2× new-customer
   acquisition via click-through.
2. **UCP won the standards race** *(confirmed)* — Google/Shopify Universal
   Commerce Protocol (NRF Jan 2026; Stripe/Adyen/Visa/MC/Amex/Walmart/Target
   endorsed). Agents probe `/.well-known/ucp/manifest.json`; capabilities bind
   to REST **or MCP** transports. ACP survives as the feed/checkout-session
   spec of the ChatGPT/PayPal ecosystem. Posture: **one backend, two protocol
   bindings.**
3. **Agent-ready product feeds are the highest-leverage item** *(partially
   verified — direction right)* — OpenAI Product Feed Spec (jsonl.gz, 15-min
   refresh, GTIN required); AI-sourced retail traffic +393% YoY in Q1 2026 and
   now converts **better** than non-AI traffic; ~$67B AI-influenced Cyber Week.
4. **Per-store MCP is default-on at Shopify** — every store exposes an
   unauthenticated storefront MCP (search/cart/checkout-URL) + `/llms.txt` +
   `/agents.md`, with trust tiers. The bar is **zero-config agent access**.
5. **Web Bot Auth** (HTTP message signatures, Cloudflare-led, May 2026) is the
   agent-identity standard; blanket bot-blocking now costs sales. Morpheus
   sits behind Cloudflare — this is a deploy-config + middleware item.
6. **Agent payments = delegated scoped credentials** (Stripe Shared Payment
   Token, AP2 mandates, Visa TAP, MC Agent Pay) — relevant *later*, given #1.
7. **Sidekick sets the assistant bar** *(confirmed)* — proactive + multi-step
   agentic + extensible. Linda's briefing/reflection/proposals queue is the
   right architecture; the missing tier is **permissioned ops autonomy**
   ("I noticed X, prepared the fix — approve?").
8. **AI product-content generation is free table stakes** *(confirmed)* —
   47% of sellers use it; Shopify/Wix bundle it. Absence is disqualifying.
9. **GEO/AEO replaces part of SEO** — being recommended by assistants is
   driven by feeds + JSON-LD + review signals; GEO monitoring tools start at
   $500+/mo — an SMB gap Morpheus can productize server-side.
10. **Open-core rules** *(partially)* — permissive core license won;
    relicensing is the unforgivable move ("will they rug-pull?" is a standard
    agency screen). Vendure's plugin-license exception is the model for
    agency-sells-proprietary-plugins.

## Codebase reality (from the 6-dimension audit)

**Genuinely strong:** commerce spine (orders/catalog/payments) is
production-grade; SEO plugin is commercial-grade (~10k lines: sitemaps,
JSON-LD, llms.txt); 8-channel feed fleet is real; three-tier storefront
search; MCP governance layer; `morpheus` SDK facade with CI-enforced API
stability; 924-line plugin manual; Linda is a real agent (post-v0.2.27:
semantic memory, reflection, briefing, propose-only self-coding).

**The hard truths:**
- **Portfolio math:** of ~104 registered plugins, ~30 production-grade,
  ~22 demo-grade/untested, **~21 shells** (the 20 "F-plugin" roadmap batch).
  "100+ plugins" as a marketing line will not survive contact with an agency
  evaluation. Seven duplicate half-feature pairs (shipping/smart_shipping,
  subscriptions/subscriptions_plus, reviews/ugc_reviews, wishlist/save_for_later…).
- **Built-but-never-rendered:** six plugins contribute `checkout_extra`
  blocks (express-pay buttons, address autocomplete, upsells) — **no template
  renders that slot**. The conversion features exist and are invisible.
- **Dead-on-arrival MCP writes:** `agent_mcp/views.py:277` rejects every
  non-read tool before cluster resolution — the admin MCP write catalog can
  be listed but never executed, contradicting docs + token manager.
- **Linda's trust defect:** `ai_assistant/integrations.py` fabricates
  `{'status':'success'}` for 20+ integrations with no HTTP call — Linda can
  report campaign sends that never happened.
- **Growth stack holes:** EmailCampaign has **no send path**; guest carts
  (majority of abandonment) never recovered; no promo-code field or cart
  quantity-edit on the live checkout; experiments engine is headless;
  referrals capture no `?ref=`; markets/multicurrency is a facade with zero
  consumers; subscriptions have no billing.
- **Admin gaps vs Shopify bar:** RBAC plugin exists but is enforced nowhere
  (any staff can hard-delete the catalog); mobile tables clipped (1 of 21
  templates has overflow-x); list views swallow DB errors into "Add your
  first product"; no bulk edit/undo; raw unformatted prices; zero admin i18n.
- **DX drift:** PLUGIN_DEVELOPMENT.md contradicts shipped code; two
  scaffolders emit different canon; hooks catalogue trapped in code comments;
  out-of-tree pip plugin path untested; no morpheus.testing factories.

## The plan — five waves

### Wave 1 — Truth & polish sprint (~2 weeks, all S/M effort)
The cheapest credibility + conversion wins; several are one-file fixes.
1. Render the dead slots: `{% storefront_blocks "checkout_extra" %}` (+
   pdp_below_gallery, order_receipt_extra) — unlocks express-pay, address
   autocomplete, upsells already written.
2. Cart quantity edit + promo-code/gift-card field on the live one-page
   checkout; fire BEGIN_CHECKOUT there (cart_abandonment/analytics are
   currently blind on the default path).
3. Kill the fake integrations layer — honest "not connected" errors + golden
   eval asserting Linda never claims an unexecuted action.
4. Fix the MCP admin write gate (route through the existing scope + approval
   governance — the whole stack is already built and tested).
5. Guest-cart recovery (use checkout-entered emails, consent-gated) +
   recovered-revenue counter.
6. Honest admin error/empty states; un-clip mobile tables; |money price
   formatting.
7. AI-traffic attribution: classify ChatGPT/Perplexity/Claude/Gemini
   referrers + AI-crawler hits server-side; revenue-by-AI-source row +
   "AI visibility" section in Linda's briefing. (No SMB tool offers this.)
8. One AI front door: collapse the 3 competing AI entry points into Linda;
   fix the home-page disable-test leaks.

### Wave 2 — Agent-ready by default (3–4 weeks)
9. Public per-store storefront MCP, default-on, unauthenticated read + cart +
   **checkout-URL handoff** (Shopify tool semantics: search_shop_catalog /
   update_cart / get_cart) — CART_TOOLS/CHECKOUT_TOOLS are empty unions today.
10. UCP manifest at `/.well-known/ucp/manifest.json` (align existing
    manifests; MCP binding reuses the cluster) + keep ACP feed as the second
    binding. **Advertise only capabilities that work** — currently manifests
    promise checkout completion that 422s.
11. Ninth channel plugin: **openai_feed** (OpenAI Product Feed Spec, 15-min
    refresh, ISBN-as-GTIN for books) + factor a shared canonical-feed
    projection for Google/Meta/TikTok/OpenAI fan-out.
12. "Agentic readiness" dashboard page: feed health, GTIN coverage, JSON-LD
    completeness, manifest status, AI-referrer revenue — Linda lints it daily
    and files fixes.
13. Web Bot Auth verification middleware + documented Cloudflare allow rules.

### Wave 3 — The Linda gap-closers (3–4 weeks)
14. **Linda Ops Inbox**: generalize the ADR-0028 propose-only queue to
    OpsProposal — reorder suggestions, stale-product flags, feed fixes,
    unfulfilled-order nudges, campaign drafts; each proposal contributed by
    the owning plugin via the hooks bus; approve = execute through existing
    rails. This is the Sidekick/Amelia interaction tier, and every
    prerequisite already shipped in v0.2.25–27.
15. AI product-content autofill on the product form (PRODUCT_FORM_CARDS
    card, per-field accept/regenerate, brand voice, then multilingual per the
    localization plan) — built on ai_content's real bulk services.
16. Retention engine: EmailCampaign send path + event-triggered flows
    (winback, post-purchase, browse-abandonment) on the proven
    cart_abandonment pattern. Email/SMS is 30–45% of healthy-merchant
    revenue; this is the largest functional hole.

### Wave 4 — Developer ecosystem + license (3–4 weeks)
17. Doc truth pass: fix PLUGIN_DEVELOPMENT.md drift; unify the two
    scaffolders; `manage.py morpheus hooks` + generated docs/HOOKS.md;
    async-hook `mode=` passthrough in the SDK (disable-gating trap);
    split CLAUDE.md (public contract vs maintainer runbook); dev llms.txt.
18. **Morpheus Dev MCP** — docs/hooks/schema/slot-registry search server for
    coding agents (Shopify Dev MCP / Medusa docs-MCP parity; Saleor has
    nothing). Reuses agent_mcp infra.
19. `morph doctor` — package the internal guards (manifest, migrations,
    boundary imports, disable-safe render check, dead-slot check) as a public
    validator; gate a curated plugin registry on it.
20. Real out-of-tree plugin path: test MORPHEUS_EXTRA_PLUGINS in CI,
    `--package` scaffold mode, example external repo, morpheus.testing
    factories. North-star metric: **agent time-to-first-plugin** (fresh
    Claude Code session → doctor-clean disable-safe plugin, unattended).
21. License commitment: permissive core (MIT/Apache) + written never-restrict
    pledge + Vendure-style plugin-license exception (rides ADR 0026).

### Wave 5 — Depth & housekeeping (ongoing)
22. Enforce RBAC across dashboard views (presets: Owner/Manager/Fulfillment/
    Content) — the "second employee" trust gap; critical for agencies.
23. Experiments UI (engine is statistically honest and fully headless);
    Shopify made native A/B testing table stakes.
24. Checkout field hygiene: ISO country select, required postal code,
    wallets at cart/PDP; consolidate the two discount engines (promotions =
    engine of record; marketing.Coupon folds in).
25. Portfolio cleanup: merge/retire the 7 duplicate pairs; move vanity
    plugins (lumina, bookstore_3d) out of the default set; "100+ plugins" →
    "~40 production plugins, honestly labeled"; dashboard authoring surfaces
    for kept F-plugin models (journal already has posts; drops/rails need UI
    or retirement).
26. Bigger bets to schedule deliberately: multicurrency (wire markets or cut
    it), subscriptions billing (Stripe), admin i18n (rides the localization
    plan), theme #2 (proves the theme contract; storefront plugin currently
    hardcodes "dot books" copy in ~8 places — fix regardless).

## What we deliberately do NOT build
- **In-agent payment completion (SPT redemption)** — the market reversed to
  discovery + handoff; revisit only if UCP checkout-in-AI regains momentum.
- A second storefront framework / headless rewrite — the monolith + themes
  is the moat for the agency motion.
- Marketplace take-rate infrastructure — 0% take rate, curated registry
  first; monetization stays hosting/support/enterprise (ADR 0026).

## KPIs
- Checkout: wallet-take %, checkout completion, recovered-cart revenue.
- Agentic: AI-referrer sessions/revenue, feed coverage %, agent MCP calls.
- Linda: briefing engagement, ops-proposals approved %, eval success rate.
- DX: agent time-to-first-plugin, doctor pass rate, external plugins count.
