# Apps consolidation (2026-10-12)

Owner, 2026-10-12: "analyse the apps, what needs to be improved, which can be merged with
others that share similar features. We have 100 apps, maybe too much?"

Yes. 115 apps in `plugins/installed/`, 109 of them on the default list, so every store runs
them. Measured on the four live stores (row counts per app, read-only): 44 apps own tables
that hold **zero rows on every store**, and 29 more have no tables at all. Four code
reviews (one per area, full tables with file:line references in
[`apps-review-2026-10/`](apps-review-2026-10/)) found the overlaps and the dead code.

**Target: about 50 apps instead of 115**, and a default list of about 35. Book and travel
verticals, supplier apps and one-off tools become opt-in. Nothing moves customer data: every
model a merge would move has zero rows, except a few config rows and the small tables named
below.

## Wave 0: live problems to fix first (one release, before any merge)

Found during the review; each is visible or exploitable on a live store today.

**Status (v0.101.0, 2026-10-12):** items 1, 2, 4, 5, 6 and 7 are fixed, except the
`post_purchase` emails (owner: "ignore mail for now"). Item 4 kept the tool and the mutation
and routed both through `RefundService.record_external` instead of deleting them, because
merchants do refund outside the store. Items 3 and 8–10 shipped in v0.113.0 (spec
`docs/superpowers/specs/2026-10-15-wave0-live-fixes-design.md`). Not done there: AI provider base URLs
need an allowlist, and the `markets` middleware goes with that app in wave 2.

1. **Paid PDFs download without signing in.** `flipbook/views.py:44-47` puts
   `product.digital_file.url` into the preview page, and `/media/digital/*.pdf` is served
   publicly: dotbooks has 510 active digital products, and
   `/media/digital/a-princess-of-mars_dotbooks_digital_edition.pdf` answered 200 with the whole
   file (checked 2026-10-12). Serve digital files from private storage through the download
   tokens `digital_products` already has; render previews server-side or from a separate,
   truncated file.
2. **A second checkout form on every checkout.** `checkout_experience` adds a "Contact /
   Shipping / Payment / Pay USD 0" form under the real one on all three shop themes; its submit
   goes to a route that does not exist. Delete the app.
3. **Consent:** five server-side conversion APIs (Meta, TikTok, Pinterest, Snapchat, Reddit)
   send the hashed email and purchase whatever the shopper chose; `meta.sync_audience` uploads
   every user with an email, staff included, under scope `analytics.read` with no approval;
   `tracking`'s Google Ads purchase tag and its second cookie banner skip the consent app.
4. **`orders.mark_refunded` (agent_core) bypasses refunds**: a queryset `update()`, so no FSM,
   no `PAYMENT_REFUNDED`, gift cards and points never re-credited. Delete it; `orders.refund`
   is the real path.
5. **False promises in the cart and on pages:** `advanced_ecommerce`'s bar always says "40 USD
   unlocks free shipping" (it compares a dict with a number); dot_books and montenegro hardcode
   "Free shipping over $40 / €40"; returns copy promises "ship within 48 hours"; the OpenAI feed
   claims 30-day returns by default; all six channel feeds are titled "Dot Books" on every store.
6. **Reviews:** any signed-in account's review is published at once and feeds the
   `aggregateRating` in structured data; nothing sets `is_verified_purchase`.
7. **Silent no-ops and soft 404s:** `post_purchase` has no beat entry, so review requests and
   NPS never send; the `/membership/` footer link is a soft 404 on every store; `rails` and
   `ugc_reviews` print empty headings on every cart, checkout and product page; montenegro's
   footer links the book apps ("Write a book", "3D store").
8. **Guardrails:** `ai_assistant/services/llm.py` is a second LLM stack that the kill switch and
   spend cap never see (store bootstrap, dashboard AI writers, SEO FAQs, description fill);
   `agent_mcp` is not protected, so switching it off leaves Linda with no tools.
9. **Per-request cost:** `ai_assistant`'s middleware writes a session (and `Set-Cookie`) for
   every anonymous visitor, crawlers included, for a value nothing reads; `environments`'
   middleware runs 1–2 queries per request while disabled.
10. **Latent:** merchant webhooks would be delivered twice (core and `webhooks_ui` both post);
    ad spend is overstated ~30× in attribution; `workflows` and `openai_shopping` POST to
    staff-entered URLs without the SSRF check.

## Wave 1: delete what does nothing (cheap, low risk)

**Status (v0.122.1, 2026-10-22):** the ten apps and the dead models left the code in v0.122.0, and
v0.122.1 drops their tables (`plugins` 0002 for the removed apps, one migration in each app that
stays; on another install, a removed app's table that still holds rows is kept).
`agent_core.AgentConversation`/`AgentMessage` stay: the agent invoke API writes them, so they move
with the AI merge in wave 2.

Zero rows everywhere and no working surface. A table-dropping migration ships first, the app
leaves the default list in the next release (two releases, so no boot ever loads a model
without its table).

`checkout_experience`, `one_click`, `rich_post_purchase`, `smart_shipping`, `referrals` (and
loyalty's dead `Referral`), `experiments`, `functions`, `environments`, `journal`,
`linda_generated`, `brand_kit`, `lumina` (recreate as a CMS page on dotbooks), and the dead
models `customers.WishList(Item)`, `agent_core.AgentConversation/AgentMessage`,
`ai_assistant.PromptTemplate/AIExperiment/DemandForecast/AgentMemory`, `marketing.Redirect`,
`observability.ErrorEvent` (1,360 stale rows on dotbooks), `morpheus_brain.DailyReport`
(fabricated "2027 trends" text).

## Wave 2: merges

**Status (v0.123.1, 2026-10-23):** wishlist ← save_for_later. save_for_later was a stub (off on
every store, nothing behind its cart button, 0 rows), so nothing moved: it left the code in
v0.123.0 and its tables in v0.123.1. Next: reviews.

One merge per release; each keeps settings keys, moves config rows in a data migration, keeps
old agent-tool names as aliases for one release, adds a `MIGRATING.md` section, and passes the
disable suite.

| Into | Folds in | Why |
|---|---|---|
| `channels` (adapters) | google_shopping, meta_commerce, microsoft_commerce, pinterest_commerce, snapchat_commerce, tiktok_commerce, openai_shopping, amazon_ads, reddit_ads | Feed, coverage and settings code is 0.8–0.9 similar; 32 functions repeat (~800 lines); 30 tools are 4 concepts. ~11k LOC → 5–6k; 17 dashboard tabs → 1. One consent-gated conversions dispatcher fixes wave 0 item 3 for good. Two steps: a shared kit first, then collapse. |
| `dropshipping` (opt-in) | dsers, zendrop, aliexpress, cjdropshipping | Four parallel link and order tables for one concept; a variant linked to two suppliers is ordered from both. One `SupplierProduct` (unique per variant) and `SupplierOrder`. |
| `product_gallery` | product_videos, product_stories, immersive_pdp, media_3d | All "media on the product page"; three of them can never render on a real PDP (GraphQL dict). Fixes the undeclared product_videos dependency every PDP has. |
| `dynamics` | personalisation, rails, discovery_quiz, advanced_ecommerce's rails | One merchandising engine. advanced_ecommerce is split: low-stock badge → inventory, free-shipping bar deleted. |
| `reviews` | trust_signals, ugc_reviews | One reviews owner; fixes the empty sections and the broken settings panel. |
| `wishlist` | save_for_later | Same concept. |
| `promotions` | marketing (coupons; campaigns → newsletter) | Coupons have four homes today; disabling promotions silently stops every coupon. |
| `payments` | advanced_payments, fraud_rules | COD and the test gateway are 60 lines; the fraud score is written where nobody reads it. |
| `orders` | returns_portal | orders already owns returns; it will also enforce the published return window. |
| `post_purchase` | post_checkout_upsell | Both are "after the order". |
| `draft_orders` | b2b quotes | Same object; nothing creates or converts a Quote. |
| `affiliates` | (referrals, deleted) | A referral is an affiliate program for customers. |
| `agent_core` (Settings → AI) | janus, ai_content, then ai_assistant's provider keys | One AI app instead of nine; one LLM stack (`core/agents/llm.py`). `morpheus_brain` moves to `core/brain`. |
| `consent` ("Privacy") | gdpr | One merchant concept, one switch. |
| `staff_mfa` ("Staff sign-in") | staff_sso | SSO must run the MFA gate. |
| `release_notes` → `system` | feedback, backups | Help, About, Version, Backups, Report a problem; protected. |
| `storefront` | pwa | Two `/sw.js` owners today. |
| `analytics` | feature_adoption, channels' ROAS page | One attribution page; `ANALYTICS_AD_SPEND` goes. |
| `agent_core` automations | workflows | Both "when X, do Y"; automations already run on Celery under the consent rules. |
| core (`core/audit`, core webhooks) | observability, webhooks_ui | Core already owns the audit log and the webhook dispatcher. |
| `book_product` ("Books", opt-in) | audiobooks, eco_impact, flipbook, bookstore_3d, bookvault | The book vertical leaves the default list; dotbooks adds it to `MORPHEUS_EXTRA_APPS` before that deploy. |
| `demo_data` ("Store setup", opt-in) | store_bootstrap | Seeding, not a live-store feature; bootstrap becomes a Janus skill. |
| (delete) | markets | Two parallel per-market price systems; this one reaches neither display nor charge price. `localization` stays. |

## Opt-in instead of default

`subscriptions`, `b2b`, `marketplace`, `cloudflare`, `importers`, `live_commerce`, the books
bundle, `dropshipping`, `demo_data`, `agentic_checkout` (already off by default). A store opts
in with `MORPHEUS_EXTRA_APPS`.

## Also found (fix inside the owning merge)

Hooks registered without an owner keep firing after a disable (`post_purchase`, `fraud_rules`,
`loyalty_points`); coupon types the form offers but the engine ignores; settings that pass the
readers guard while nothing reads them (`motion`, `media_3d`, `ai_stylist`); phantom `requires`
that log a boot error when the target is disabled; manifests describing features that do not
exist; stale external API versions (Google Ads v17, Content API v2.1, Shopify 2024-01, Graph
v21.0); `rbac` writes to the database from `ready()`; missing Janus tools for bookings,
vendors, book metadata, customers and suppliers; ~9.7k LOC of store-specific seed content in
shared apps.

## Order

Wave 0 (one release) → wave 1 (two releases) → wave 2, cheapest first: wishlist, reviews,
post_purchase, payments, orders/returns, promotions, gallery, dynamics, consent, staff sign-in,
system, pwa, analytics, automations, core audit/webhooks, AI, books bundle, dropshipping,
channels last (largest, medium risk).
