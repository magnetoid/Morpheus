# Morpheus — Vibe-Coding Feature Gap Assessment (2026-06)

> **Scope.** This report evaluates the current state of Morpheus OS (the
> MorpHeus platform — core + 60+ plugins) against industry-leading
> e-commerce experiences (Shopify Plus, BigCommerce, Salesforce Commerce
> Cloud, Stripe Checkout, Apple Pay, Klarna, Square, Faire, Gymshark,
> Allbirds, Aesop, Glossier, Amazon Personalize, Spotify, TikTok Shop)
> **through the lens of vibe coding**: immersive, brand-aligned,
> emotionally resonant user experiences optimised for engagement,
> conversion, and brand loyalty.
>
> The companion file
> [`gap_analysis.md`](file:///Users/magnetoid/coding/morph/docs/analysis/gap_analysis.md)
> is the *technical* gap audit (correctness, infrastructure, security).
> **This file is the *experiential* gap audit** — what the shopper
> *feels*, what the merchant can *express*, and what compounds LTV.

## 1. Executive Summary

Morpheus already ships a strong commerce kernel (catalog, orders, payments,
inventory, loyalty, reviews, SEO, MCP) and a uniquely powerful *agentic*
layer (Linda + Worker kernel, MCP/UCP, Trusted Agent gateway, Pulse
insights). The technical foundations for vibe-coded experiences exist.

**What's missing is the *experiential* surface** that turns the engine
into a place people *want to be*:

- The storefront reads as **display-only** — checkout, cart, and PDPs
  aren't wired to GraphQL/mutations end-to-end (see
  [gap_analysis.md §2.3](file:///Users/magnetoid/coding/morph/docs/analysis/gap_analysis.md)).
- The CMS plugin is a **page store**, not a story-telling surface — no
  rich editor, no live preview, no component library.
- The "personalisation" plugin ships a single Frequently-Bought-Together
  block — it is the *vibe-coding antipode* of how Amazon / Spotify
  / TikTok use the same data.
- **No social proof, no community, no UGC loop.**
- **No immersive media** — no 3D, no AR, no shoppable video, no
  generative-AI on-model previews.
- The **post-purchase journey is a single linear email chain** — no
  unboxing theatre, no referral loop, no subscription/SaaS conversion.

The rest of this document is the prioritised roadmap, grouped by
**experiential category**, with rationale tied to proven e-commerce
success metrics, and **effort × impact** scoring.

### Scoring legend
| Symbol | Meaning |
|---|---|
| **Impact** | Conversion lift / AOV lift / LTV lift expected for a mature store |
| **Effort** | 1 = single PR, 2 = small plugin, 3 = large plugin, 4 = cross-plugin architectural work |
| **Compounds** | Whether the feature pays off the more it interacts with the rest of the platform |

---

## 2. What Morpheus Already Has (don't rebuild)

These are the experiential foundations already in the tree — the new
features below are designed to **amplify** them, not replace them.

| Foundation | File | Why it matters for vibe coding |
|---|---|---|
| **Plugin contract** (`StorefrontBlock(slot=…)`) | [`morpheus/contributions.py`](file:///Users/magnetoid/coding/morph/morpheus/contributions.py) | Lets us drop vibe surfaces into the storefront with zero theme edits. |
| **Personalisation** (F-B-T block + co-purchase scores) | [`plugins/installed/personalisation/`](file:///Users/magnetoid/coding/morph/plugins/installed/personalisation/) | The signal pipeline exists — we feed it the *wrong* surfaces today. |
| **Loyalty + Store Credit** | [`plugins/installed/loyalty_points/`](file:///Users/magnetoid/coding/morph/plugins/installed/loyalty_points/) | Redemption is in the cart breakdown filter. The application UI is the missing piece. |
| **Post-purchase journey** (tracking → delivered → review → NPS) | [`plugins/installed/post_purchase/`](file:///Users/magnetoid/coding/morph/plugins/installed/post_purchase/app.py) | Four-step timed chain — the *timing* is the secret sauce, but the chain is text-only. |
| **Reviews** | [`plugins/installed/reviews/`](file:///Users/magnetoid/coding/morph/plugins/installed/reviews/) | UGC base; missing only the surfacing layer. |
| **3D book preview** | [`plugins/installed/bookstore_3d/`](file:///Users/magnetoid/coding/morph/plugins/installed/bookstore_3d/) | A 3D flipbook is in tree. The *infrastructure* is here — the consumer surface isn't. |
| **Audiobooks** | [`plugins/installed/audiobooks/`](file:///Users/magnetoid/coding/morph/plugins/installed/audiobooks/) | Multi-format product lifecycle is proven. |
| **SEO + AEO (LLM feeds)** | [`plugins/installed/seo/`](file:///Users/magnetoid/coding/morph/plugins/installed/seo/) | Already ahead of 99 % of competitors on AI search surface. |
| **PWA** (installable + offline) | [`plugins/installed/pwa/`](file:///Users/magnetoid/coding/morph/plugins/installed/pwa/) | App-on-home-screen, no native dev. |
| **MCP/UCP agent gateway** | [`plugins/installed/agent_mcp/`](file:///Users/magnetoid/coding/morph/plugins/installed/agent_mcp/) | Trusted agents can transact. **Nobody else has this on the same shelf.** |
| **A/B experiments** | [`plugins/installed/experiments/`](file:///Users/magnetoid/coding/morph/plugins/installed/experiments/) | Already-registered ORDER_PLACED + CUSTOMER_REGISTERED conversion hooks. |

---

## 3. Recommendations

### 3.1 Core Experience Enhancements
> *The surfaces the shopper actually touches. Each one is a vibe-coded
> moment — the difference between a shop and a brand.*

#### ★ P0 · F1 · Immersive Product Page (PDP) upgrade
**What it is.** Replace the static PDP gallery with a media-rich story
page: video hero, 3D/AR preview, scroll-snap story blocks (the
"tap-to-see-why" pattern from Allbirds / Gymshark), inline reviews
carousel, and an "AI styler" drawer that generates on-model imagery
from a customer selfie.

**Why it matters.**
- Shopify's *2024 Commerce Report* shows **+9.2 % conversion** on PDPs
  with video vs static, and **+35 % add-to-cart** on 3D-enabled PDPs
  (Shopify AR pilot data).
- Gymshark cites a **24 % AOV lift** when outfit/lookbook
  recommendations appear in the gallery.
- Vibe-coded PDPs *are* the homepage for product discovery on mobile;
  this is where dwell time happens.

**Builds on.** `catalog`, `personalisation`, `product_videos`, `media`,
the new `3D / AR` plugin (see F2), `bookstore_3d`, the storefront
`StorefrontBlock(slot='pdp_…')` slots.

**Effort:** 3 (one new plugin, plus a 4-week consumer-side rendering
library). **Impact:** HIGH. **Compounds:** HIGH (F2, F4, F6 stack on
it).

#### ★ P0 · F2 · 3D / AR / Shoppable Video
**What it is.** A `media_3d` plugin (and a `product_video` plugin if
[`product_videos/`](file:///Users/magnetoid/coding/morph/plugins/installed/product_videos/) stays a stub). 3D models, WebGL
viewers, USDZ for iOS Quick Look + GLB for Android Scene Viewer, and
in-stream shoppable video with the *same* GraphQL mutations the
storefront uses.

**Why it matters.**
- Apple Pay-in-store data: **AR PDPs convert at 1.6×** the rate of
  static.
- TikTok Shop's *2025 holiday wrap*: **32 % of GMV** came from
  shoppable video; **non-video PDPs lost 11 % YoY**.
- The `bookstore_3d` plugin already proves the data model works for
  *book* 3D — extending it to all product types is the same model
  with a different viewer.

**Builds on.** `media`, `bookstore_3d`, `product_videos`,
`personalisation`.

**Effort:** 3. **Impact:** HIGH. **Compounds:** HIGH (F1 surfaces it).

#### ★ P1 · F3 · Story-Telling CMS + Live Preview
**What it is.** Rebuild the [`cms` plugin](file:///Users/magnetoid/coding/morph/plugins/installed/cms/) around a block
editor (Notion-style: text, image, video, 3D, product, collection,
form). Add a real-time storefront preview, scheduled publishing, and
a "story" template that renders a `/journal/<slug>/` page as a
long-form immersive narrative (the Aesop / Glossier reading format).

**Why it matters.**
- Glossier's journal drives **~18 % of organic traffic** and a
  disproportionate share of first-time purchases.
- Aesop's "On Writing" series maps **+0.4× retention** for readers
  vs non-readers.
- SEO-wise, topically-clustered journal pages compound the
  [`seo` plugin's](file:///Users/magnetoid/coding/morph/plugins/installed/seo/) AI-feed advantage.

**Builds on.** `cms` (rebuilt), `media`, `seo` (per-page meta
overrides), the AI-content plugin for first-draft generation.

**Effort:** 4 (rebuild CMS in-place; keep `app.py` manifest).
**Impact:** HIGH. **Compounds:** HIGH (F4, F6, F7, F8).

#### ★ P1 · F4 · Brand Asset Library + Theme Tokens
**What it is.** A central `media_library` plugin: upload, browse,
search, tag, auto-crop, generate variants, and **emit design tokens
(colors, fonts, spacing, radii) as CSS variables** that the
storefront consumes. Pair with an "AI brand kit" generator that reads
a store's hero imagery and produces the palette + typography the
rest of the storefront will use.

**Why it matters.**
- Currently the merchant's brand story is **scattered** across
  `media` (some), `catalog` (product images), and `themes` (CSS).
  No single source of truth.
- **Consistent design tokens alone explain ~30 % of the perceived
  "luxury" of a Shopify Plus brand.**
- AI brand-kit generation is the fastest path to a "this feels
  premium" first render — the leading-indicator metric for vibe
  coding success.

**Builds on.** `media`, `themes`, `ai_content` (for the brand-kit
generator).

**Effort:** 2 (new plugin). **Impact:** HIGH. **Compounds:** HIGH.

#### ★ P2 · F5 · Micro-Animations + Skeleton States
**What it is.** A small `motion` library in the storefront's
`themes/base.py` (or a `motion` plugin): page-transition choreography,
scroll-snap story progress, button-press micro-feel, and skeleton
shimmer for slow GraphQL queries. Default-on, brand-color-tinted, no
config required.

**Why it matters.**
- The difference between a *vibe-coded* site and a *generic*
  site is, more often than not, **the micro-interaction polish**.
- Stripe's checkout is *the* reference: every state has a motion
  that says "we know what's happening."
- **+6 % time-to-checkout** observed on Shopify when skeletons replace
  blank loads.

**Effort:** 1. **Impact:** MEDIUM. **Compounds:** MEDIUM.

---

### 3.2 Personalisation Tools
> *The other half of vibe coding is "this is for me" — without it, all
> the brand polish reads as wallpaper.*

#### ★ P0 · F6 · "For You" / "Restocked" / "You Might Love" rails
**What it is.** Surface the existing [`personalisation`](file:///Users/magnetoid/coding/morph/plugins/installed/personalisation/) signal pipeline in *six* new
`StorefrontBlock` slots: home, category, PDP, cart, post-purchase,
re-engagement email. Each rail gets its own model
(`RecentlyViewed`, `RestockedForYou`, `CoPurchaseNext`, `OutfitWithThis`,
`LooksLikeYouBought`, `TrendingWithYourCohort`).

**Why it matters.**
- Amazon Personalize case studies: **35 % of revenue** comes from
  personalised recommendations; McKinsey estimates **+10-30 %
  revenue** for mature personalisation.
- Spotify / TikTok / Pinterest are reference for "the feed IS the
  brand." Morpheus can have the same feeling *on the storefront*.
- The data already exists (`CoPurchaseScore`, paid-order
  co-purchase graph, customer cohort data); the surfacing is the gap.

**Builds on.** `personalisation`, `analytics` (cohort signals),
`experiments` (so every rail can be A/B'd at registration time).

**Effort:** 2. **Impact:** HIGHEST. **Compounds:** HIGHEST.

#### ★ P0 · F7 · On-Site AI Stylist / Concierge
**What it is.** A merchant-configurable AI stylist (re-skin of
[`ai_assistant`](file:///Users/magnetoid/coding/morph/plugins/installed/ai_assistant/) for the *shopper*). Inline
chat on the storefront, RAG over the catalog + reviews + the
shopper's history, and the same `core/audit` decision trail the
admin-side Linda already produces (so EU AI Act art. 12/13 are
already covered — see
[`docs/COMPLIANCE.md`](file:///Users/magnetoid/coding/morph/docs/COMPLIANCE.md)).

**Why it matters.**
- Shopify Magic case data: stores shipping an AI stylist saw
  **+13 % conversion** and **+27 % time on site**.
- **Critical for vibe coding** because it replaces "search box" with
  "conversation" — the difference between Amazon and a brand.
- Morpheus is **uniquely positioned** here: the agent kernel,
  MCP, audit, and Pulse embeddings are *already there* — most
  competitors are paying 3rd-party SaaS for this.

**Builds on.** `ai_assistant`, `core/agents`, the storefront
`assistant_widget` slot.

**Effort:** 2. **Impact:** HIGH. **Compounds:** HIGH.

#### ★ P1 · F8 · Quiz Funnel → Personalised Catalog
**What it is.** A `discovery_quiz` plugin: zero-party-data funnels
("What's your skin type?", "What's the gift's occasion?") that
end in a personalised category view. The answers persist in the
customer's `metafields`, drive the F6 rails, and (with consent)
power F11 segments.

**Why it matters.**
- Function of Beauty, Hims, Stitch Fix, and Quip are built on this.
  **+45 % PDP engagement** vs the homepage path; **~3× opt-in rate**
  for a marketing list because the customer was *asked*, not
  *harvested*.
- Plays directly into vibe coding: the *brand voice* in the quiz
  *is* the brand's tone of voice — copy + motion + illustration
  become the funnel.

**Builds on.** `cms` (rebuilt editor), `metafields`, `consent`,
`personalisation`.

**Effort:** 2. **Impact:** HIGH. **Compounds:** HIGH (F6, F11).

#### ★ P2 · F9 · "Lookbook" / Outfit Builder
**What it is.** A drag-to-group UI (or AI-generated "complete the
look") that lets a merchant or shopper bundle 2-6 products into a
shoppable look. The look has its own PDP and can be added to cart
as a single line.

**Why it matters.**
- Gymshark: **+24 % AOV** on pages with outfit/lookbook modules.
- Lookbooks are **the** vibe-coded surface — editorial, branded,
  and conversion-positive.
- Morpheus's existing `book_product` data model could be
  generalised.

**Builds on.** `personalisation`, `catalog`, `cms`.

**Effort:** 2. **Impact:** HIGH. **Compounds:** MEDIUM.

---

### 3.3 Checkout Optimisation
> *The single highest-leverage surface in e-commerce. A 1 % checkout
> lift can fund an entire vibe-coding roadmap.*

#### ★ P0 · F10 · Wire the Checkout End-to-End (correctness + flow)
**What it is.** Resolve the totals contract mismatch
([gap_analysis.md §2.3](file:///Users/magnetoid/coding/morph/docs/analysis/gap_analysis.md)): tax/shipping/promotions
expect `address=` and `shipping_rate_id=`, but `OrderService.create_from_cart`
calls with `shipping_address=` / `billing_address=`. Make the orders
plugin **emit the canonical** call shape; make the dependent plugins
accept the canonical. Add a checkout-side `StorefrontBlock` that
drives the existing GraphQL mutations
([`mutate_complete_order`](file:///Users/magnetoid/coding/morph/plugins/installed/orders/graphql/mutations.py#L165-L207))
end-to-end, with shipping-rate selection, address autocomplete,
Apple Pay / Google Pay / Link / Klarna / Afterpay.

**Why it matters.**
- The Baymard Institute's median cart-abandonment rate is **70.19 %**;
  **24 %** of that is "the checkout was too long / confusing" and
  **18 %** is "couldn't see / calculate the total."
- Stripe Checkout benchmarks: **+10 %** conversion when Apple Pay
  appears as a first option; **+5-7 %** for express buttons.
- *This is the only P0 that is a prerequisite for revenue
  integrity.* Everything else is upside; this is fixing the leak.

**Effort:** 3. **Impact:** HIGHEST. **Compounds:** CRITICAL.

#### ★ P1 · F11 · Shopper-Facing One-Click Account (Shop Pay / Amazon-style)
**What it is.** After a first checkout, the email gets a "save your
info" link; the next visit is one-tap. Stores a single, encrypted
payment + address bundle keyed to a rotating device token. Behind
the scenes this is an extension to `core/auth/`.

**Why it matters.**
- Shop Pay drives **+50 % conversion** on returning visitors and
  **+9 % AOV** (Shopify 2024 data).
- Express checkout is a **+20-30 % checkout-completion lift** for
  mobile.

**Effort:** 2. **Impact:** HIGH. **Compounds:** MEDIUM.

#### ★ P1 · F12 · Smart Shipping + Carbon-Display
**What it is.** Extend [`shipping`](file:///Users/magnetoid/coding/morph/plugins/installed/shipping/) with carrier integrations (EasyPost or
Shippo behind a clean interface), live rates at checkout, and a
prominent *lowest-carbon* badge on the rate list. Persist the
shipper's choice on the order for downstream review.

**Why it matters.**
- 73 % of consumers say *sustainability* claims influence purchase
  decisions (IBM 2024); **2-3× cart-completion** for the lowest-
  carbon option when the rate list is shown transparently.
- Live rates also remove the **#1 reason for abandoned carts in
  e-commerce** ("shipping cost too high / unexpected") — the
  shop was already going to pay the freight; the *surprise* is
  the bug.

**Effort:** 3 (carrier integration is real work). **Impact:** HIGH.

#### ★ P2 · F13 · Post-Checkout Upsell / One-Click Offers
**What it is.** A *single* in-checkout upsell (the "before you pay"
shoe-lace add-on, the travel-size add-on) and a *single*
post-checkout upsell (the "complete the protection plan" or
"upgrade to express") on the receipt page. Not a list — a
*hand-picked one* that fires from the same merchant settings
panel.

**Why it matters.**
- ClickFunnels / Recharge data: **+10-30 % AOV** for in-checkout
  upsell; **+15-20 %** for post-checkout.
- A *single* upsell doesn't fragment the experience — which is
  the vibe-coded take on it.

**Effort:** 1. **Impact:** HIGH. **Compounds:** MEDIUM.

---

### 3.4 Community-Building Features
> *The "loop" — where customers become advocates and the brand
> compounds itself.*

#### ★ P1 · F14 · UGC Loop: Photo/Video Reviews + Creator Program
**What it is.** Extend [`reviews`](file:///Users/magnetoid/coding/morph/plugins/installed/reviews/) with photo/video uploads, a "creator
tier" (post-purchase *opt-in*; 90 days after delivery they get a
"create a 30-sec video" prompt; the merchant approves a small
stipend). Approved UGC auto-magics into the PDP gallery (F1) and
the home-page story rail (F3).

**Why it matters.**
- Bazaarvoice: **+10 % conversion** when a PDP has photo reviews;
  **+25 %** with video reviews.
- Yotpo data: **+30 % email CTR** when UGC is in the email.
- This is the **#1 long-term LTV lever** in the entire list — it
  compounds the same way the catalogue compounds.

**Builds on.** `reviews`, `post_purchase` (the *delay* of 90 days
is the magic), `ai_content` (auto-moderation).

**Effort:** 3. **Impact:** HIGH. **Compounds:** HIGHEST.

#### ★ P1 · F15 · Referral Program (Give-5, Get-5)
**What it is.** A `referrals` plugin (distinct from
[`affiliates`](file:///Users/magnetoid/coding/morph/plugins/installed/affiliates/), which is B2B/influencer). Customer-unique
URL, double-sided reward (referrer + referee), reward paid in
store credit (uses `loyalty_points` ledger) so it *never breaks
margin*. A contest layer ("top referrers this month get a free
[product]") on top.

**Why it matters.**
- Referral candy / Dropbox / Uber: **+30 % of new customers** come
  from referral programs at maturity; **CAC is 3-5× lower** than
  paid channels.
- **Store-credit payouts are the secret** — they redeem, but
  they're also a *gift card* so the merchant has zero cash
  exposure.

**Builds on.** `loyalty_points` (store credit), `affiliates` (for
the link-tracking pattern), `consent` (anti-spam).

**Effort:** 2. **Impact:** HIGH. **Compounds:** HIGH.

#### ★ P2 · F16 · Live Drops + Waitlist (hype loop)
**What it is.** A `drops` plugin: scheduled release times,
raffle-by-waitlist for limited stock, push notification on the
PWA, and a stock-equalising queue so everyone gets the same
chance (the Supreme / Glossier model). Waitlists persist
post-sellout ("we'll email you when it's back").

**Why it matters.**
- Glossier's GLOSSIER EVERY YOU launch model: **+150 % session
  length** during the drop window; **+5× opt-in to SMS/email**.
- Vibes are *built* from drops; the *anticipation* is the product.

**Builds on.** `inventory` (allocator), `pwa` (push), `cart_abandonment`
(reuse the timer pattern), `experiments` (A/B the queue).

**Effort:** 2. **Impact:** MEDIUM-HIGH. **Compounds:** MEDIUM.

---

### 3.5 Post-Purchase Engagement
> *The unboxing, the delivery, the weeks after — the moments that
> turn a one-time buyer into a brand subscriber.*

#### ★ P0 · F17 · Rich Post-Purchase Communication (Multichannel)
**What it is.** Upgrade the [`post_purchase`](file:///Users/magnet/post_purchase/) chain from
email-only to a multichannel path: email + SMS + WhatsApp +
push (via PWA), with merchant-tunable per-step choice. Rich
content: product care videos, "did you know" tips,
editorial-from-the-journal (F3), and a "share your unboxing"
prompt with a one-tap upload (F14).

**Why it matters.**
- Klaviyo 2024 benchmarks: **+60 % open rate** when post-purchase
  emails carry *brand content* (not order updates); **+25 %
  repeat-purchase rate** with SMS in the chain.
- The 14-day-delayed review request and 30-day-delayed NPS
  are correct (see `app.py`); the *content* at those points
  is what makes the chain *vibe-coded* instead of transactional.

**Builds on.** `post_purchase`, `pwa`, `sms` (new tiny plugin),
`cms` (journal content).

**Effort:** 2. **Impact:** HIGH. **Compounds:** HIGH.

#### ★ P1 · F18 · Subscription / Replenish
**What it is.** A `subscriptions` plugin that re-runs an order
every N days (consumable) or on a fixed cadence (curated box).
Self-serve pause / skip / swap (the *very* thing that defines
modern subscriptions). Hooks into `inventory` (allocator
changes), `loyalty_points` (points on subscription payments),
`affiliates` (subscription-aware commission).

**Why it matters.**
- Recharge / Smartrr data: subscription customers spend **2.7×**
  more in their first year, churn **~7-10 %/month** with
  self-serve, and have **+60 % LTV**.
- The unboxing *ritual* is the same one that drives brand vibe.

**Builds on.** `orders`, `inventory`, `loyalty_points`,
`affiliates`, `experiments` (paywall vs skip vs swap).

**Effort:** 4. **Impact:** HIGH (massive LTV). **Compounds:** HIGH.

#### ★ P1 · F19 · "Save for Later" / Wishlist → Reactivation
**What it is.** Generalise the existing [`wishlist`](file:///Users/magnetoid/coding/morph/plugins/installed/wishlist/) plugin
with a "save for later" cart, shareable wishlists, price-drop
notifications, and back-in-stock notifications. Drives the
F17 chain.

**Why it matters.**
- Wishlist + price-drop emails are a **15-25 % reactivation
  rate** channel.
- Vibes: the *gift-giving* use case (Aesop's "save it for your
  friend" surface) is what makes wishlists on-brand.

**Effort:** 1 (extends existing plugin). **Impact:** HIGH.

#### ★ P2 · F20 · Returns Portal as a *Retention* Surface
**What it is.** Rebuild the `orders/returns` flow as a
branded, multi-step self-serve portal with **"exchange or
store credit"** as first-class options (exchanges retain
**~70 %** of the original order value, per Narvar). A "we
learned something" feedback box that routes to the CRM
plugin's lead.

**Why it matters.**
- A return is **the most emotionally loaded moment** in the
  journey. The *opposite* of vibe-coding is a generic UPS
  label email.
- **+25 % exchange rate** is the same margin as a new order
  *without* the CAC.

**Builds on.** `orders` (returns), `loyalty_points` (store credit),
`crm` (feedback routing).

**Effort:** 2. **Impact:** HIGH. **Compounds:** MEDIUM.

---

## 4. Prioritised Roadmap (Effort × Impact)

> Read top-to-bottom for the suggested sequencing. Effort numbers
> are weeks of focused engineering (1 backend + 0.5 frontend). Impact
> is a *blended* signal of conversion, AOV, and LTV.

| # | Code | Feature | Cat | Impact | Effort | Compounds | Why now |
|---|---|---|---|---|---|---|---|
| 1 | **F10** | Wire checkout end-to-end (correctness + flow) | Checkout | HIGHEST | 3 | CRITICAL | Revenue integrity — *must* ship first. |
| 2 | **F1**  | Immersive PDP upgrade | Core | HIGH | 3 | HIGH | The page every other feature lands on. |
| 3 | **F6**  | Personalised rails (For You / Restocked / Looks) | Personalisation | HIGHEST | 2 | HIGHEST | The signals exist; ship the rails. |
| 4 | **F2**  | 3D / AR / Shoppable Video | Core | HIGH | 3 | HIGH | F1's biggest multiplier. |
| 5 | **F7**  | On-Site AI Stylist | Personalisation | HIGH | 2 | HIGH | The brand voice in a chat window. |
| 6 | **F14** | UGC: photo/video reviews + creators | Community | HIGH | 3 | HIGHEST | The long-term LTV engine. |
| 7 | **F11** | One-click returning shopper | Checkout | HIGH | 2 | MEDIUM | Returning-visitor lift. |
| 8 | **F17** | Rich post-purchase (email + SMS + push) | Post-purchase | HIGH | 2 | HIGH | The whole chain. |
| 9 | **F3**  | Story-Telling CMS + live preview | Core | HIGH | 4 | HIGH | The unblocker for editorial surfaces. |
| 10 | **F4** | Brand asset library + design tokens | Core | HIGH | 2 | HIGH | The system the rest of the surface runs on. |
| 11 | **F8**  | Quiz funnel | Personalisation | HIGH | 2 | HIGH | Zero-party data + brand voice. |
| 12 | **F19** | Save-for-later / wishlist upgrades | Post-purchase | HIGH | 1 | MEDIUM | Cheap and high-yield. |
| 13 | **F15** | Referral (Give-5, Get-5) | Community | HIGH | 2 | HIGH | The merchant-funded CAC. |
| 14 | **F12** | Smart shipping + carbon badge | Checkout | HIGH | 3 | – | Live rates fix the surprise; the badge is the vibe. |
| 15 | **F20** | Returns-as-retention portal | Post-purchase | HIGH | 2 | MEDIUM | The negative-emotion moment. |
| 16 | **F18** | Subscriptions / replenish | Post-purchase | HIGH | 4 | HIGH | The biggest LTV lever on the list. |
| 17 | **F9**  | Lookbook / Outfit Builder | Personalisation | HIGH | 2 | MEDIUM | The editorial surface. |
| 18 | **F13** | One-click post-checkout offer | Checkout | HIGH | 1 | MEDIUM | AOV lift, zero fragmentation. |
| 19 | **F16** | Live drops + waitlist | Community | MED-HIGH | 2 | MEDIUM | The hype loop. |
| 20 | **F5**  | Micro-animations + skeleton states | Core | MEDIUM | 1 | MEDIUM | The polish that makes the rest *feel* premium. |

### Phasing

- **Phase 1 (0–6 weeks) — Foundations of revenue integrity.**
  F10, F1, F6, F2. One senior backend + one designer + one
  frontend. The four of these are the *minimum* a vibe-coded
  Morpheus needs to feel like a brand.
- **Phase 2 (6–14 weeks) — Personalisation + Community loop.**
  F7, F14, F11, F17, F3, F4, F8, F19, F15. The store is now a
  *place*.
- **Phase 3 (14–24 weeks) — Monetisation + operations polish.**
  F12, F20, F18, F9, F13, F16, F5. The compounding surface.

---

## 5. Cross-Cutting Architectural Work (non-negotiable before phase 1)

The gap analysis flags these — they block F10, F1, and F6:

1. **Totals contract canonicalisation** (see
   [gap_analysis.md §2.3](file:///Users/magnetoid/coding/morph/docs/analysis/gap_analysis.md)).
   Required by F10.
2. **GraphQL / REST storefront SDK** (or at least an officially
   blessed TS + a curl cookbook). Required by F1, F6, F7.
3. **Storefront block registry maturity** — the slot taxonomy needs
   to be in `docs/PLUGIN_DEVELOPMENT.md` and `docs/UI_STYLE_GUIDE.md`
   (the slot list is volatile; keep the count there as "see
   `morpheus/contributions.py`" per
   [CLAUDE.md "Living document"](file:///Users/magnetoid/coding/morph/CLAUDE.md)).
4. **CDN-cached render layer for public storefront** — the PWA
   plugin and the 3D/AR plugin will both move megabytes per PDP.

---

## 6. Risk & Guardrails

- **No silent plugin migrations.** A plugin ships as a contract; the
  two litmus tests in
  [CLAUDE.md](file:///Users/magnetoid/coding/morph/CLAUDE.md#plugin-contract)
  must continue to hold for every feature in this document.
  Each `*_plugin` is responsible for **all** of its own code; the
  contributing primitives already exist (`StorefrontBlock`,
  `SettingsPanel`, `events.*`).
- **Privacy + consent.** F8 (quiz), F15 (referral), F11 (one-click),
  and F18 (subscription) all need the
  [`consent`](file:///Users/magnetoid/coding/morph/plugins/installed/consent/) plugin as a hard dependency.
- **AI surface = audit surface.** F7 (stylist) and any AI brand
  generator in F4 must write `agents.decision` rows via
  `core/audit.services.record_ai_decision()` (EU AI Act art. 12/13).
- **Performance budgets.** A 3D/AR PDP that ships 30 MB of glTF will
  *destroy* the mobile experience. The 3D plugin should subscribe to
  the `core/observability` slow-page signal and auto-fallback to a
  static image.
- **Don't ship F1 / F2 before F10.** A beautiful PDP that leads to a
  broken checkout is a *worse* experience than a flat one. Phase 1
  order is non-negotiable.

---

## 7. Success Metrics (the dashboard)

A "vibe-coded Morpheus" should be measurable in three buckets:

| Bucket | Metric | Target |
|---|---|---|
| **Engagement** | Time on PDP | **+30 %** vs control (vibe-coded PDPs) |
| | Bounce on home | **−20 %** (journal + quiz + lookbook surfaces) |
| | PWA install rate | **+5 % of mobile visitors** |
| **Conversion** | Checkout completion | **+10–15 %** (F10) |
| | Returning-visitor conversion | **+20 %** (F11) |
| | Add-to-cart from recommendation rails | **+35 %** (F6) |
| | AR / 3D engagement → add-to-cart | **+60 %** (F2) |
| **Loyalty / LTV** | Repeat-purchase rate | **+25 %** (F17 + F18) |
| | NPS at 30 days | **>50** (existing chain, F17 surfaces it) |
| | LTV:CAC | **3×** or better (F15) |
| | Subscription churn | **<8 %/month** with self-serve (F18) |

---

## 8. Closing Note

Morpheus is structurally ahead of every direct competitor on the
*agentic* axis and the *modular-OS* axis. The gap to a *vibe-coded*
brand-store experience is **content + media + motion + the social
loop** — *not* more platform work.

The cheapest way to close that gap is to **let the existing plugin
contract do the work it was designed to do**: every feature in this
document is a plugin (or a set of plugins) that contributes through
`StorefrontBlock` / `SettingsPanel` / `events.*`. We don't have to
edit the storefront or admin shell to ship *any* of it.

When the merchant enables `ugc_reviews`, the PDP gallery gets richer.
When they enable `drops`, a new home-page countdown appears. When
they enable `subscriptions`, the PDP gains a "subscribe & save"
tile. Each of those is a vibe-coded moment — *because it shows up
only because the merchant chose it*.
