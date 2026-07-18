# Morpheus OS — Release Notes

Detailed, user-facing updates to the **Morpheus OS core** and its modules,
surfaced in **Dashboard → Settings → Version & updates**.

> **House rule (enforced):** merging to `main` is a production deploy, so
> **every deploy MUST bump `MORPHEUS_VERSION` and add a matching dated
> `## vX.Y.Z — YYYY-MM-DD` entry** here describing the change. This file is the
> single source of truth for the in-dashboard changelog. See
> [`CLAUDE.md`](../CLAUDE.md) and torsor ADRs "Versioned release notes" + **0032**
> (every production deploy bumps the version).

---

## v0.21.0 — 2026-07-18

**EU digital-goods withdrawal waiver at checkout.** Selling downloadable books
(ebooks, audiobooks) in the EU requires the buyer's express consent to
immediate access *and* their acknowledgement that this waives the 14-day right
of withdrawal (Directive 2011/83/EU art. 16(m)) — otherwise a customer can
download the file and still demand a refund. Now:

- When a cart contains any digital/downloadable item, a **required
  acknowledgement checkbox** appears at checkout (both the one-page and
  multi-step flows). The order can't be placed until it's ticked.
- The exact wording is **merchant-editable** (Settings → Checkout & cart) —
  ships with a common default, which you should review with your own counsel.
- The accepted acknowledgement (the exact text shown + a timestamp) is
  **recorded on the order** as the compliance artifact.
- Physical-only carts are never gated.

**Ships disabled by default** — enable it under Settings → Checkout & cart once
you've finalised the wording. The mechanism is in place; no checkbox appears at
checkout until you switch it on.

---

## v0.20.0 — 2026-07-18

**Sales surfaces: sellable gift cards + the receipt-page upsell.**

- **Gift cards are now sellable.** Create a virtual product with the SKU
  `GIFT-CARD` (configurable under Settings → Gift cards) and every paid unit
  auto-issues a real gift card worth its price, emailed to the buyer with the
  code (merchant-editable template). Idempotent against webhook replays —
  one card per unit, never doubles. Books are gift-native; now the shop is too.
- **"You might also like" on the order confirmation page.** The receipt now
  renders the post-order upsell: the merchant-configured pick (Settings →
  Post-checkout upsell), falling back to the newest arrival the customer
  didn't just buy. Renders through the `order_receipt_extra` block slot —
  previously contributed but never rendered by the theme — so any plugin can
  now add receipt-page surfaces, and disabling the upsell plugin removes it.

---

## v0.19.0 — 2026-07-18

**The email marketing engine is live.** Morpheus could capture subscribers and
send transactional email, but campaigns had no send path — the biggest missing
marketing primitive. This release completes it:

- **Send campaigns.** New dashboard page (Marketing → Send campaigns) targets
  any Email Campaign at your confirmed, double-opt-in subscriber list — with a
  **test-send to yourself** first. Sending is queued, idempotent (a re-run or
  double-click never double-mails anyone), counts recipients, and marks the
  campaign sent.
- **Inbox-compliant by construction.** Every bulk send carries the RFC 8058
  one-click-unsubscribe headers Gmail/Yahoo require, plus a visible
  unsubscribe footer; the unsubscribe endpoint now honours the one-click POST.
  The core email sender gained a `headers` passthrough for this.
- **Win-back flow.** When a customer slips into the at-risk RFM segment
  (nightly rescore), confirmed subscribers get a warm "we saved some books for
  you" email — consent-gated (no subscription, no email), max one per address
  per 30 days, with an optional configured coupon code (Newsletter settings).

Owned by the newsletter plugin end-to-end (disable it and the send page,
routes, win-back, and emails all vanish). Covered by 8 new tests including
header assertions and dedupe windows.

**Security fixes** (from the July application audit, verified then patched):

- **GraphQL cache isolation.** The query cache keyed on query+variables only,
  so an authenticated caller's response could be served to other users for up
  to 5 minutes. Authenticated sessions and Bearer-token callers now bypass the
  cache entirely (read and write); anonymous storefront traffic keeps it.
  Regression-guarded by cross-user isolation tests.
- **Bulk customer delete now respects the staff guard.** Single-record delete
  always refused staff/superuser accounts; the bulk action didn't — a sweep
  selection could hard-delete an admin. Bulk delete now skips staff accounts
  with a warning, exactly like the single-record path.

---

## v0.18.0 — 2026-07-18

**Spend your reader points at checkout.** Loyalty points have been earnable
for a while, but there was no way to *spend* them — the discount math existed,
the checkout wiring didn't. This completes the money path:

- **Cart control** — a "You have N reader points (worth $X)" panel in the cart
  lets a signed-in shopper apply points toward their order (capped to their
  balance), or remove them. Self-hides for guests and zero-balance customers.
- **Ledger debit at checkout** — when an order is placed, the redeemed points
  are actually debited from the balance (a single `spend_order` ledger row),
  inside the same atomic block as gift-card redemption. Idempotent: a retried
  checkout never double-spends.
- **Automatic reversal on cancel** — cancel an order that spent points and the
  points come straight back (a shopper is never out points for an order that
  didn't ship). Idempotent against a paid cancel firing both cancel + refund.

The whole flow is disable-safe (the control, routes, debit, and reversal all
vanish if the loyalty plugin is turned off) and covered by 13 tests, including
the real `create_from_cart` and `order.cancel()` paths.

---

## v0.17.1 — 2026-07-18

**Fix: the mood-search landing is now reachable.** In v0.17.0 the natural-language
"describe what you're in the mood for" panel lived on the `/search/` empty state,
but a query-less `/search/` was 302-redirecting straight to `/products/` — so no
one clicking **Search** ever saw it. `/search/` now renders the mood-search
landing; a keyword search (`/search/?q=…`) still bounces to the rich product-list
page as before. Regression-guarded by `storefront/tests/test_search_landing.py`.

---

## v0.17.0 — 2026-07-18

**Book-native quick wins** — first batch from the ideas roadmap (research-backed:
Baymard AOV data, review-conversion studies, book-discovery patterns).

- **"Add €X for free shipping" progress bar in the cart.** When a free-shipping
  threshold is configured, the cart now shows how close the order is with a
  progress bar — the cheapest proven lever for average order value (shoppers add
  items to qualify), and it kills the "unexpected shipping cost" surprise that's
  the #1 cart-abandonment driver. Self-hides when no free-shipping rule is set.
- **The review-request email now links straight to each book's review form.**
  The post-purchase "how was your order?" email (sent ~2 weeks after delivery)
  used to be a generic nudge; it now lists every book on the order with a
  one-click link to write that review. Reviews are the single biggest
  conversion asset for books.
- **Mood search — "just describe what you're in the mood for."** The search
  page now invites natural-language queries ("a short novel that feels big",
  "like Normal People but hopeful") with example prompts, routed through the
  existing AI/semantic search. A genuinely indie-bookshop way to discover, and
  something the big retailers' keyword filters can't do.

*Ops (no code):* recovered from a disk-full production outage — freed 37GB,
deleted the compromised crawl4ai container permanently, and added automated
disk pruning + a disk-space alert so it can't recur silently.

## v0.16.0 — 2026-07-17

**Cancel an order (right of withdrawal)** — Batch 2 of the professionalism
roadmap, EU consumer-law compliance.

- Customers can now **cancel an order themselves before it's dispatched**, from
  the order page in their account — the pre-shipment right of withdrawal that EU
  consumer law requires. A cancelled order that was already paid is **refunded
  in full automatically**, through the same safe, idempotent refund path the
  dashboard uses (the payment provider can't be double-charged); the refund
  confirmation arrives by email as usual.
- The button only appears while the order can still be cancelled — once it has
  shipped, the customer uses "Request a return" instead. The confirmation step
  is a plain expand-to-confirm control (no accidental one-click cancels, and no
  JavaScript required).

**Fixed**

- **A broken chat widget in the storefront's bottom-left corner is gone.** The
  unfinished "AI stylist" assistant was contributing a storefront widget that
  shipped without any styling or behaviour, so it rendered as raw stray text
  ("Aria / Ask me anything…") stacked in the page corner. It's withheld until
  the feature is actually built — the working "Chat with us" widget is
  unaffected.

*Still ahead in Batch 2 (needs your input):* a product-safety panel on book
pages (GPSR — requires appointing an EU Responsible Person), a digital-download
withdrawal-waiver checkbox at checkout, an accessibility (WCAG 2.1 AA) pass, and
real legal copy to replace the seeded placeholders.

## v0.15.5 — 2026-07-17

**Trust & deploy-safety quick wins** — first code batch of the July
professionalism roadmap (see `docs/plans/` research: Baymard, EAA/GDPR, CWV).

- **Branded 404 and 500 pages.** A mistyped or expired URL used to dead-end on
  Django's bare one-line "Not Found"; a crash showed a blank server error. Both
  now land on dot-books-styled pages — the 404 offers search and a way back to
  the shelf, the 500 is fully standalone so it renders even when the app can't.
- **The shop has a favicon.** Every visit requested `/favicon.ico` and got a
  404 (visible in every browser console). A dot-books mark (ink tile, red dot)
  now serves at the conventional path and is week-cached.
- **"Reject all" is as prominent as "Accept all"** in the cookie banner — same
  fill, same size. Regulators (CNIL) fine asymmetric banners; ours no longer
  visually nudges toward consent.
- **Deploys verify themselves.** `/api/readyz` now reports the running version,
  and a new `deploy-smoke` workflow polls production after every push to main
  until it converges on the pushed version and the homepage answers 200 —
  a missed webhook or wedged build queue is now a red X instead of a silent
  stale deploy. GHCR image builds also wait for CI to pass instead of
  publishing `latest` from red commits.
- **Sentry is one env var away.** The error-tracking wiring already shipped;
  `.env.coolify.example` and the operations runbook now document the
  `SENTRY_DSN` switch that turns it on.
- **Operations runbook rewritten** to match the real production topology
  (Coolify, not the aspirational k8s notes) including stuck-deploy-queue
  recovery, rollback, and backup-restore practice.
- Removed the dead synchronous order-email path (`orders/email.py` + its
  Celery wrapper) — production has long sent all order mail through the
  retrying `deliver_email` queue; the order-confirmation test now exercises
  that live path.

*Shop operations shipped alongside (no code):* the footer's Privacy / Terms /
Imprint links now resolve (pages seeded and published), outbound mail is
DKIM-signed (selector published in DNS, joining existing SPF + DMARC), and the
server no longer advertises its stack in response headers.

## v0.15.4 — 2026-07-17

**Storefront hero**

- **The book's shadow is physical now.** Each slide threw its shadow in its own
  direction — slide 4 threw it *upward*, putting the sun underneath the book —
  in its own colour (violet, green, rust), while the whole thing crawled around
  on an endless loop. One fixed light now lights every slide, so the shadow
  always falls the same way, in one neutral ink. Slides still differ, but along
  the axis that stays honest: how high the book floats — a higher float throws
  further, blurs wider and lands fainter, as a real shadow does. The shadow is
  also the book's own silhouette rather than a round smudge beside it.
- **It fades in and settles.** The shadow slides out from under the book as it
  fades, like the book rising into its float — then stops. Reduced-motion
  keeps the shadow, drops the drift.
- **The copy no longer jumps between slides.** Book titles run one to three
  lines and the sale badge only exists on discounted books, so the price and
  buttons landed at a different height on every slide. Every slide now reserves
  the same space, so the staggered fade-in reads as choreography instead of the
  page reflowing under you.

**Fixes found by an adversarial review of this batch**

- **Filtered book lists showed the wrong intro.** `/products/?genre=…`,
  `?topic=…`, `?collection=…` and price filters were treated as unfiltered, so
  a genre's results carried the sitewide "everything we shelve" intro — and
  shipped it as that page's search-result description too.
- **"Write N missing intros" could promise work it would never do.** The button
  counted terms differently from the job it starts: a genre whose books were all
  drafts was advertised as missing an intro that the job then skipped forever,
  so the number never moved however often you clicked. Both now read from one
  definition. The same page also stopped issuing one query per row (~1,500 on
  Topics).
- **Re-clicking the button no longer double-bills.** A run now holds a lock, so
  an impatient second click can't queue an overlapping batch of paid AI calls.
- **A stunted AI answer can't auto-publish**, while the Generate button still
  shows you whatever came back — the guard belongs where nobody is reviewing.

## v0.15.3 — 2026-07-17

- **Fixed: a garbled AI reply could publish itself.** When the model returned
  broken or cut-off JSON, the copy writer fell back to using that raw text as
  the intro — which briefly put a literal `{` on the live Drama genre page. A
  reply that can't be read, or is too short to be an intro, now counts as a
  failed generation: the page keeps its existing copy and the run reports a
  skip, so re-running just picks it up. (A model that answers in plain prose
  instead of JSON is still accepted — that's what the fallback is for.) The one
  affected page has been cleared.

## v0.15.2 — 2026-07-17

- **AI copy generation: the retry now gets time to finish.** v0.15.1 taught the
  gateway to retry when a reasoning model spends its whole token budget
  thinking — but thinking that long also outruns the 20 second network timeout,
  so half the retries traded an empty answer for a timed-out one. The retry now
  carries its own 45 second budget (still inside the 60 second request limit, so
  it returns copy instead of killing the worker). Measured on the live store:
  the genre backfill went from 1-of-5 pages written to writing them properly.

## v0.15.1 — 2026-07-17

- **Fixed: AI features silently produced nothing on reasoning models.** Found
  while running the new bulk copy writer against the live store, which wrote 1
  page and skipped 4. Reasoning models (the configured `deepseek-v4-pro`,
  DeepSeek's reasoner, OpenAI's o-series) spend tokens *thinking* before they
  answer, and that thinking counts against the reply's token budget. Every
  Morpheus AI feature asks for a small budget sized for ordinary models — 400
  to 600 tokens — so the model used the entire allowance reasoning and returned
  a **successful but empty** answer. Nothing errored; the copy just never
  appeared. Any dashboard "Generate" button, product-description writer or SEO
  draft on such a model was affected. The gateway now recognises that exact
  response and retries once with room to finish (measured: ~915 tokens needed
  where 400 was offered).

## v0.15.0 — 2026-07-16

**Every listing page can have an intro now — and the AI can write the backlog.**
An audit of why category/collection/author/genre pages showed no description
found three different causes; this fixes all three.

- **Genres and Topics landing pages can hold intro copy at all.** `/genres/`
  and `/topics/` looked supported but were dead through three layers: the view
  discarded the intro, the model couldn't store one (its choices omitted both
  kinds), and the dashboard hid the "Edit landing page" button for exactly
  those two. All three are open — edit them under **Products → Book
  taxonomies → Edit landing page**, same as Authors or Publishers.
- **The /products/, /vendors/ and /journal/ intros are editable.** These pages
  own no record of their own, so their intro prose — and their search-result
  description — were hardcoded with no way in. They now read a **CMS → Blocks**
  entry (`products_intro`, `vendors_intro`, `journal_intro`); the house copy
  stands in until you write one.
- **New: write missing intros in bulk.** Products → Book taxonomies now offers
  *"Write N missing intros"* per Genres/Topics — it writes the most-stocked
  pages first (the ones shoppers actually land on), runs in the background, and
  never touches copy you wrote yourself. Batched, because each page is one AI
  call; run it again for the next batch.
- Under the hood: the per-page Generate button and the bulk backfill now share
  one prompt, so they write in the same voice.

*Why most pages looked blank:* the plumbing was mostly fine and the copy was
simply never written — 1,526 of 1,527 topics and 36 of 43 genres had no intro.
The bulk writer above is the fix for that part.

## v0.14.9 — 2026-07-16

- **Storefront hero: the per-slide 3D shadows are actually visible now.**
  v0.13.1's "strange shadow behind each featured book" shipped invisible,
  twice over: the blob's dense core sat *behind* the opaque cover (only its
  near-transparent fringe ever reached the page), and the grid-card
  "minimal cover shadow" rule silently out-ranked the hero cover's base
  shadow. Each slide's shadow mass now emerges from behind the book's edge
  into the open left flank of the hero — a different organic shape, tint,
  offset and blur per slide (compact low slump / tall violet drape / sharp
  low pool / floating rust overhang), still drifting and crossfading with
  the slides. Tuned and verified against the live storefront at every
  slide position.

## v0.14.8 — 2026-07-16

UX plan P0 batch — every item is a user-facing bug from the
`dashboard-ux-consistency-2026-07` audit:

- **Creating a product, customer, or coupon no longer fakes success.** The
  three New forms returned HTML to their AJAX submits, so invalid input
  showed "Saved" while nothing was saved. They now return the real
  validation errors, and a successful create navigates straight to the new
  record's edit page (staying on the filled-in form invited an accidental
  duplicate).
- **8 hidden settings panels are visible again.** Agentic Commerce Protocol,
  one-click checkout, post-checkout upsell, and returns portal (now under
  Payments), journal (Sales channels), fraud rules (Developer),
  post-purchase flows (Marketing), and trust signals (General) had declared
  categories that don't exist — no card, no nav entry, dead URL.
- **AI settings page shows every AI plugin's panel.** It previously
  hardcoded brand voice only; AI stylist's settings were unreachable.
- **Deleting a webhook now asks first** (proper confirm dialog with
  consequences, danger-styled button).
- **Gift cards sidebar entry links to the real page** instead of a doubled
  `/apps/gift_cards/gift_cards/` path; Bookings nav entry declared a valid
  sidebar target.
- **Tracking settings dropped two do-nothing fields** (GA4/GTM "mirror"
  inputs that were never read — the real settings live at Tracking).
- **Enforcement so this can't regress:** a new `manage.py check` rule fails
  the build when a settings panel declares an unknown category or a
  dashboard page an unknown nav target (`morpheus.E001`/`E002`), with tests
  pinning the contract.

## v0.14.7 — 2026-07-16

- **Bookvault token is now write-only in Settings.** The stored API token
  was echoed back into the settings form; it now renders masked and a blank
  submit keeps the existing secret (house `format: password` convention —
  found by the UX/settings audit).
- **Dashboard & Settings consistency audit.** A four-track audit (components,
  settings surfaces, navigation, copy/feedback) produced a ranked, phased
  polish plan at `docs/plans/dashboard-ux-consistency-2026-07.md` — P0 bug
  fixes through copy standards, each with an enforcement test so fixes stick.

## v0.14.6 — 2026-07-16

- **Fixed: cart totals API crash during checkout.** The `cartTotals` GraphQL
  query (used by the checkout page's totals refresh) crashed on every call —
  the resolver reached its sibling through `self`, which is empty for root
  queries. Found via a production log sweep during a checkout audit; the
  lookup is now a shared helper and the query executes against the real
  schema in a regression test.

## v0.14.5 — 2026-07-16

- **Fixed: "AI provider error … All AI providers degraded".** Continuing a
  conversation in which Linda had used a tool could crash every strict AI
  provider (DeepSeek et al. reject a `tool` message that doesn't directly
  follow its `tool_calls`): replayed history never carried the tool-call
  ids, and long-conversation compaction could split a tool-call pair at the
  summary boundary. Tool history now replays as assistant-visible text
  (same recall, always valid), and compaction keeps tool-call pairs
  together. Guarded by `core/assistant/tests/test_message_contract.py`.

## v0.14.4 — 2026-07-16

- **Linda's knowledge stays fresh automatically.** Her RAG knowledge index
  now rebuilds itself nightly (4:30am) — previously it had no refresh
  schedule at all, freezing at the last manual rebuild, so books, language
  editions, and descriptions added after a deploy were invisible to her.
  The rebuild is incremental (unchanged content is skipped, removed content
  is pruned). The production index was also refreshed immediately
  (174 → 183 chunks).

## v0.14.3 — 2026-07-16

- **One subscription system.** Two parallel, incompatible `Subscription`
  models had shipped (the billing one in `subscriptions`, and a never-wired
  replenish/curated skeleton in `subscriptions_plus`). Merged: the
  Subscriptions app now owns delivery subscriptions too — a `kind` on every
  subscription (plan / replenish / curated box), box contents
  (`SubscriptionLine`), a shipment schedule, and a pause/skip/swap audit log,
  plus the "Subscribe & save" PDP block and the cadence/swap-window settings.
  The `subscriptions_plus` plugin is deleted. *(Post-deploy one-off: its four
  empty tables can be dropped — `subscriptions_plus_subscription`, `_line`,
  `_shipment`, `_event` — plus their `django_migrations`/`content_types`
  rows; they held zero rows.)*
- **Guest purchases now count in experiments.** Checkout stamps the anonymous
  visitor id onto the order (`Order.metadata['visitor_id']`, new `metadata`
  field), so A/B-test conversions from customers who never log in are finally
  attributed — the loop the merchandising autopilot learns from. Previously
  only signed-in conversions counted.
- **"Bought together" counts every real purchase.** The co-purchase job
  filtered on two order statuses that don't exist and missed
  processing/shipped/delivered orders; it now uses the canonical paid-status
  set, so recommendations learn from every actual sale.

## v0.14.2 — 2026-07-16

- **Mega-menu covers load ~100× lighter.** The Featured-books thumbnails in
  the Authors/Genres/Topics dropdown menus were the last images on the
  storefront still loading raw multi-MB `/media/` PNGs. They now go through
  the responsive-image proxy like the product cards (AVIF/WebP, 200/400px
  renditions sized for the ~120px tiles).

## v0.14.1 — 2026-07-16

Internal hardening release — plugin-boundary debt repayment. No new features,
nothing to reconfigure.

- **Apps now unplug cleanly from the Products screen.** The product list's
  Bookvault column, its "Send to Bookvault" bulk action, and the fulfilment
  panel on the product form are contributed through the plugin bus (new
  `PRODUCT_LIST_COLUMNS` extension point + the existing product-form cards)
  instead of being hard-coded into the dashboard. Disabling the Bookvault app
  now removes every trace of it — and this fixes a lurking crash where the
  whole Products page could error out if the app was disabled while still
  configured.
- **One breadcrumb builder.** Eight apps carried their own copy of the
  dashboard breadcrumb helper; it's now a single SDK function
  (`morpheus.dashboard_trail`). No visual change.
- **Linda's `workflows.run` tool moved into the Workflows app** — owned by the
  app it drives, like the earlier metafields tool move. The core→plugin import
  baseline shrank from 11 to 9 entries.

## v0.14.0 — 2026-07-16

- **Language editions — customers can buy books in their own language.** A
  translated edition is a full product (its own page, own-language copy, and
  its own **print / e-book / audiobook** variants), linked to the original via
  the new **"Translation of"** field on the book card (enter the original's
  slug; linking to a translation resolves to the original automatically).
  Linked editions get:
  - a **"Read it in your language"** switcher on the product page (edition
    chips with native language names — *français*, *deutsch*, …), contributed
    by the book_product plugin so it disappears if the plugin is disabled;
  - **`hreflang` alternate links** between all editions of the work — the SEO
    item deferred since the 2026-07 audit now ships where it's real.
- **Product page — variant badges.** Audiobook variants now show an
  **Audiobook** badge (they wrongly showed "Physical"); physical editions now
  read **Print**. (book_product plugin 0.2.0 → 0.3.0.)

## v0.13.4 — 2026-07-15

**Storefront design deep-dive — bugs found on the live site, fixed at the root.**

- **Card excerpts no longer show raw code.** Product cards across the home
  rails, author pages and facet pages displayed literal `&lt;p&gt;` /
  `&#x27;` fragments. Three-layer fix: the `first_sentence` filter now
  normalises stored copy to plain text (unescape entities twice + strip
  markup), the card template avoids the `{% firstof … as %}` double-escape,
  and 13 catalog rows storing pre-escaped HTML in `short_description` were
  cleaned in place.
- **Card covers load ~30× lighter.** Cards fed by GraphQL dicts (home rails,
  hero shelf) rendered the raw `/media/` originals — multi-megabyte PNGs
  (Moby-Dick: 2.9 MB) that painted as blank cream boxes while downloading.
  They now go through the same AVIF/WebP responsive proxy as everything else
  (~65 KB at grid size).
- **Add-to-cart buttons align** across a card row regardless of title/excerpt
  length (card body flexes, actions pin to the bottom).
- **Shelf pages standardized** — categories, collections, genres, topics,
  authors, publishers, series and tags now share one hero pattern: breadcrumb,
  kind eyebrow (Category / Genre / Author / Tag / …), display title with the
  accent dot, and the **dashboard-editable description** as the lede. Filtered
  shelf views (`/products/?author=…`, `?publisher=…`) now show the same
  editable copy as the term's own landing page instead of generic filler.
  Every kind was already editable in the dashboard (Categories, Collections,
  Book taxonomies, Tag descriptions) — the storefront just never showed some
  of it.
- **Home "Browse the shelves" fixed** — it linked top-level *categories* to
  `/genre/…` URLs (wrong page) and showed a single lonely chip; it now renders
  the curated genre index (same source as the mega-menu) and hides below 3
  entries.

## v0.13.3 — 2026-07-15

- **Footer rebuilt.** Removed the duplicate **Imprint / Imprints** link and split
  the overloaded "The press" column into clean **Explore** and **Sell** columns
  (Shop · Explore · Sell · Help). Legal links (Privacy, Terms, Imprint, Cookie
  preferences) moved out of the nav columns into the **bottom bar** where they
  belong — contributed via a new `footer_legal` slot (still disable-safe: turning
  off GDPR removes them). This also fixes the `Imprint`/`Imprints` collision.
- **Product page — "Recommended for you" aligns left.** It no longer indents/
  centres inside the details column: contributed PDP blocks now sit flush-left
  with the rest of the column.
- **Product page — "Recently viewed" is now a carousel of up to 20.** The
  recently-viewed rail switched from a fixed grid of 8 to a horizontal,
  scroll-snap **carousel** remembering the visitor's last **20** books.

## v0.13.2 — 2026-07-15

- **Fix — audiobook sample player never appeared on the storefront.** The PDP
  passes `product` as a GraphQL dict, but the `audiobook_for` tag filtered the
  variant FK by that dict — which raised and was silently swallowed, so the
  "🎧 Listen to a sample" block rendered nothing even for a ready audiobook. The
  tag now resolves the id from either a dict or a model.
- **Audiobook editions are their own variant type.** An audiobook edition is no
  longer created as a generic **Digital** variant — it's now `variant_type =
  'audiobook'`, so it reads as an audiobook everywhere (dashboard, agent tools,
  API). It still behaves as a downloadable, no-shipping edition: checkout skips
  inventory reservation and the download is delivered exactly as for digital
  variants. (Metadata-only migration; existing digital audiobook variants keep
  working — re-save or run the backfill to re-type them.)

## v0.13.1 — 2026-07-15

- **Storefront — book shadows.** The hero slider now casts a **different strange
  3D shadow behind each slide** — every featured cover gets its own organic
  blob shape, tint, offset and drift, so the shadow visibly morphs as the slider
  advances (crossfades with the active slide; disabled under
  `prefers-reduced-motion`). Book covers in the grids now carry a **minimal**
  resting shadow that grows **slightly** on hover, replacing the heavier lift.

## v0.13.0 — 2026-07-15

- **Linda gets a knowledge base (RAG, phase 1).** Linda can now retrieve
  **unstructured** knowledge — the platform docs (Architecture, Plugin
  Development, Release Notes, API, Quick Start) and any plugin-contributed
  sources — and cite it in-chat, complementing her existing live tool-calls
  (structured data like orders/inventory stays on exact tool-calls; RAG only
  adds what she otherwise can't see). Architecture per ADR 0017: the retriever
  **seam lives in core** (`core/assistant/knowledge.py`) and the ai_assistant
  plugin registers the actual retriever in its `ready()` — so core imports no
  plugin, and disabling ai_assistant cleanly removes the knowledge block from
  the prompt. Plugins contribute their own documents through the new
  `KNOWLEDGE_SOURCES` filter (same pattern as `BRAIN_SIGNALS`). Build/refresh the
  index with `python manage.py rebuild_knowledge`. Embeddings are stored as JSON
  (Python cosine) at current scale; a pgvector index is the planned phase 2
  (`docs/plans/rag-knowledge-base.md`).

## v0.12.7 — 2026-07-15

- **Fix — book pages with no category no longer 500.** The PDP eyebrow used
  `{{ genre.name|default:product.category.name|default:… }}`; Django resolves
  every `|default:` argument eagerly, so `product.category.name` was evaluated
  even when a genre existed — and any book with **no category** (`category` is
  `None`) crashed with `VariableDoesNotExist`. Rewritten with `{% firstof %}`,
  which resolves each candidate with `ignore_failures=True` and tolerates a
  `None` category. (Only `giants-bread` was affected today, but it was a latent
  crash for every category-less book.)
- **Storefront grid — capped at 5 across + roomier edges.** The book grid
  (`.grid-books`, all listing pages) no longer expands to 6/7 columns on very
  wide screens — it holds at **5 per row** from 1280px up, so covers stay a
  legible size. Page gutters widen on large desktops (3.25rem ≥1280px, 4.5rem
  ≥1600px) for more breathing room at the edges; mobile/tablet unchanged.
- **Footer — capped width, no empty gap.** The footer columns and sign-off no
  longer stretch edge-to-edge on wide screens; content is capped at 1400px and
  centered. The newsletter confirmation line no longer reserves a blank gap
  under the Subscribe form when empty (its `aria-live` announcement still fires
  on success).
- **Dashboard — micro-animation polish.** Sub-nav **tabs** now grow their
  underline from the left (faint on hover, full on active) instead of snapping;
  the **confirm dialog** backdrop fades in with the card's pop; **KPI stat
  tiles** deepen their shadow on hover so they feel alive. All interaction-only
  (no new page-load animations) and neutralised under `prefers-reduced-motion`.

## v0.12.6 — 2026-07-14

### Product page: cleaner recommendations + full-height cover

- **Dynamic product blocks can now hide titles** (new "Show title" toggle in
  Merchandising, alongside "Show price"). Turn both off for a clean
  image-only recommendation grid.
- **Product cover shows in full.** The main image on the product page now fits
  the whole cover at full height instead of cropping it to fill.

---

## v0.12.5 — 2026-07-13

### Accessibility: wordmark link name matches its visible text

The header logo link advertised the accessible name "Home" while showing the
"dot books" wordmark, so voice-control users saying "click dot books" couldn't
activate it (Lighthouse `label-content-name-mismatch`). Its accessible name is
now the visible wordmark — the storefront PDP now passes Lighthouse at 100 for
Accessibility, Best Practices, and SEO.

---

## v0.12.4 — 2026-07-13

### SEO: real return policy in product structured data + sitemap cleanup

- **Return policy now appears in Product structured data.** Google's 2026
  merchant listings expect a return policy; product markup now carries the
  store's actual return window (read from the Returns plugin's configured
  window — never a fabricated value, and it disappears if that plugin is
  disabled). Previously it was omitted unless a separate SEO field was set.
- **Image sitemap trimmed to what Google still uses.** Dropped the
  `<image:caption>` and `<image:title>` tags Google deprecated (only
  `<image:loc>` carries meaning now).

---

## v0.12.3 — 2026-07-13

### Dashboard sidebar: submenus stay open across navigation

Opening a sidebar submenu no longer collapses when you move to a page in a
different section. The section (and hardcoded parents like Orders/Products) you
were browsing stays expanded as you navigate; collapsing one still sticks until
you reopen it.

---

## v0.12.2 — 2026-07-13

### Fix: Subscriptions dashboard page returned a 500

The **Subscriptions** dashboard page (`/dashboard/apps/subscriptions/`) crashed
with a server error: the view sorted subscriptions by a `created_at` field the
model doesn't have. Now sorted by `started_at` (the subscription's actual
creation timestamp). No data change.

---

## v0.12.1 — 2026-07-13

### Verified external references on book pages (SEO)

New `apply_external_links` tool adds a "Sources and references" section to book
descriptions, linking out to authoritative sources — Open Library, WorldCat, and
(when confirmed to exist) the author's Wikipedia page. Every link is built from
identifiers we already store or verified live before it's written, so there are
no broken/invented outbound links. Available to the dashboard AI as
`seo.apply_external_links` (approval-gated) and preserved across description
regenerations.

---

## v0.12.0 — 2026-07-13

### Storefront hero: full-height, auto-fitting titles, a floating book

The home hero now fills the viewport, and each featured title **auto-fits** —
long or short book names both settle into a tidy, professional block instead of
overflowing or shrinking to nothing. A soft 3D shadow drifts slowly behind the
cover so the book reads as floating (respects reduced-motion).

### Book form: searchable Genre & Topic pickers

In the dashboard product form, **Genres** and **Topics** are now searchable
multi-select dropdowns — type to filter, tick several — instead of long checkbox
walls.

### SEO fixes

- **Filtered listing pages now get a real title.** Tag, author, publisher, and
  search result pages were all titled "All books"; they now reflect the actual
  filter (and so do the page's structured-data name, breadcrumb, and social
  preview). Tag pages also use their editorial copy as the meta description.
- **Pagination no longer hides deep products.** Page 2+ of a listing used to
  canonicalise back to page 1 (which can de-index later products); each page now
  self-canonicalises, per current Google guidance.

### DeepSeek AI provider

Selecting **DeepSeek** in Settings → AI now works. The provider was offered in
the picker but had no driver wired up, so it errored with "Unknown AI provider";
it's now a first-class OpenAI-compatible provider (deepseek-chat /
deepseek-reasoner).

---

## v0.11.1 — 2026-07-13

### Fix: tag pages returned a 500 on production

The v0.11.0 tag landing pages (`/products/?tag=…`) crashed with a server error
on the live site. Root cause: products use a UUID primary key, but the tag
system (taggit) was wired through its default table whose object-id column is an
integer — so every tag lookup asked Postgres to compare a UUID against an
integer and failed. (Local SQLite is loosely typed and silently accepted it, so
tests passed while production broke — the classic "SQLite hid a Postgres bug".)

Tags now route through a UUID-typed join, so tag pages load and products can
actually be tagged. No action needed; existing data is unaffected.

---

## v0.11.0 — 2026-07-13

### Tag pages get a proper title + description

Every browse taxonomy — categories, collections, genres, topics — already showed
an editorial description below its title. **Tags** were the exception: a tag page
(`/products/?tag=<tag>`) had only a generic header. Now each tag can have its own
attractive title + description, written under **Products → Tag descriptions** in
the dashboard and shown below the title on the tag page. Tag links also resolve
more reliably (matched by slug or name).

## v0.10.0 — 2026-07-12

### Storefront polish + a round of fulfilment fixes

**Storefront.** The homepage no longer opens with a "Recommended for you" block
above the hero — the editor's-picks hero leads the page again. The "New &
notable" and "Staff picks" rows are now horizontal **carousel sliders** (swipe on
touch, arrow buttons on desktop) instead of tall grids.

**Order fulfilment (fixes).**

- **Manual "mark paid" now actually delivers.** Marking an order paid from the
  dashboard (for COD, bank transfer, or any out-of-band payment) used to only
  flip a flag — it never ran the fulfilment steps, so digital downloads weren't
  sent, loyalty points weren't awarded, and the payment-confirmed email never
  went out. Now it completes the order properly, once.
- **Bulk cancel works.** Cancelling several orders at once was silently doing
  nothing (and still reporting success); it now cancels them and releases their
  stock.
- **No more duplicate download emails** if an order's payment is confirmed twice.
- **Fixed runaway abandoned-cart processing** that was re-notifying and re-running
  recovery on every stale cart every half hour.

**Under the hood.** Consolidated duplicated internal helpers (conversions-API
payload builders, dashboard breadcrumbs) — no behaviour change.

## v0.9.0 — 2026-07-12

### Your shop now protects money, data, and shoppers' rights

A platform-wide correctness and compliance pass. The headline items are things
that could quietly lose money or data before this release.

**Money is safe at checkout and in refunds.**

- **No more overselling.** Two shoppers can no longer both buy the last copy.
  Stock is now reserved inside the order transaction with a hard gate — a
  short-stock order is refused and rolled back instead of being created and
  charged.
- **Refunds actually move money.** Refunds issued from the returns portal or by
  the AI assistant used to email the customer "refunded" while nothing happened
  at the payment provider. They now route through the real gateway, exactly like
  the dashboard refund button, and only send the "refunded" email once the money
  has genuinely moved.
- **No over-refunds.** A refund can never exceed what was actually paid, on any
  path (returns, assistant, or dashboard).
- **Gift cards can't be given away free.** If a gift card fails to apply at
  checkout (expired, disabled, already spent), the order is refused rather than
  charging the discounted total and eating the card.
- **Coupon limits hold under load.** A limit-one coupon can no longer be used
  twice by two simultaneous checkouts.
- Refund amounts now use the correct minor-unit conversion for every currency
  (yen, dinar, …), and each refund has its own idempotency key.

**Security.** Closed two stored-cross-site-scripting holes: product rich text is
now sanitised on save, and structured-data (SEO) output is properly escaped, so
a malicious product name or description can't run scripts on shoppers.

**GDPR / privacy (new `gdpr` module).** A self-service privacy hub in the account
area: shoppers can **download all their data** and **delete their account**, and
the storefront footer now carries **Privacy, Terms, and cookie-preference**
links (seeded legal pages included). Every request is logged for your records.
Cookie consent is now honoured correctly end-to-end — "Accept all" actually
enables analytics and personalisation (three mismatched consent signals were
unified into one). Turn the whole surface on or off under Settings → General.

**Order emails & account.** Order-confirmation emails are no longer sent two or
three times, and are sent reliably in the background with retries instead of
holding up checkout. Order status now shows correctly on the account pages
(it was blank).

**Operations.** Database backups are fixed: the image now ships `pg_dump`,
backups are written to a persistent volume that survives redeploys, and a failed
backup is now loud (logged + surfaced) instead of silently reporting success.
An internal event table that grew forever on every page view is now bounded.

## v0.8.1 — 2026-07-12

### Linda fails gracefully — and her actions are on the record

- **No more raw error dumps in chat.** When every AI provider is down, Linda
  now says what's wrong and what to do ("The active AI provider has no API
  key configured — open Settings → AI…") instead of printing
  `[All AI providers degraded …]` with a stack trace. The failure also
  reports the *configured* provider's real error — previously an
  unconfigured fallback's noise masked the actual cause.
- **Fallback only uses providers you've configured.** Providers without an
  API key no longer join the failover chain (each one used to burn a full
  timeout before failing).
- **Everything the AI writes is auditable.** Linda's write-tool calls,
  background Workers' actions, and their real outputs now land in the audit
  log — previously chat transcripts were the only record.
- **Sandbox locked down.** Linda's script sandbox is read-only for real:
  three tools that could quietly write or delete rows from inside scripts
  are now correctly gated. The legacy `/api/mcp/tools/*` endpoint (which
  accepted unauthenticated requests) now requires a staff session.
- **Settings tell the truth.** Two switches that were connected to nothing
  ("Agent purchases require approval", "Memory confidence decay") have been
  removed until the code behind them exists.

### The self-improvement loop actually heals now

- **Fixed an inert pipeline.** The engine's analyzer and its healers used
  two different naming schemes, so every approved fix ended in "no healer
  found" — the loop scanned, planned, and then did nothing. SEO gaps now
  route to the alt-text and meta-description healers, zero-result searches
  to the synonym healer, dead links to the redirect healer.
- **The safety boundary reaches your commits.** A new pre-commit gate blocks
  hardcoded secrets, raw destructive SQL, and `os.system` from ever being
  committed — and `extra_protected_paths` in settings now genuinely extends
  the AI-write protection boundary.

## v0.8.0 — 2026-07-11

### The storefront feels alive — microanimations everywhere

- **Covers morph into the product page.** Click any book on the shelf and its
  cover glides into place as the product page opens (cross-document view
  transitions), instead of a hard cut.
- **The brand period stamps itself.** Every big heading ends in the red
  dot-books period — it now presses into the page as the heading scrolls into
  view, like a type slug hitting paper.
- **The page responds as you read.** Product grids cascade in with a gentle
  stagger, a 2px red *reading ribbon* under the top bar tracks your progress
  down the page, and the top bar lifts and goes translucent once you scroll.
- **Adding to cart finally confirms.** The button flips to **“✓ Added”** while
  the cover flies to the bag, the drawer springs open with items cascading in,
  and the subtotal pops when its value changes.
- **Dozens of small touches** — prices tick when you switch editions, FAQ
  answers unfold, footer links nudge, ghost buttons invert to ink, search
  results and the mobile menu cascade in. Everything honours
  *prefers-reduced-motion* and works without JavaScript.

### The storefront feels printed — visual craft + real content

- **Paper with tooth.** The warm background now carries a faint print-stock
  grain; covers get a **spine crease and edge light** so books read as
  physical objects.
- **Missing covers become title pages.** Products without an image render a
  set title page — hairline frame, the title in Fraunces, the red period
  beneath — instead of an apologetic “No image yet”.
- **Bookish typography.** Drop caps open the product description and journal
  entries, prices are set in the serif, every section eyebrow carries a short
  red tick, and the footer signs off with a colophon.
- **Real content on the home page.** The journal teaser now shows your actual
  latest journal entries (with correct links and dates), and a new **“Browse
  the shelves”** genre index renders your top-level categories as a
  contents page.

## v0.7.0 — 2026-07-11

### A real account page

- **Settings → Your account** is now editable. Set your **first and last name,
  phone, and company** — saving your name means the top-right menu finally
  shows it instead of your email. The page also shows your account details, a
  **two-factor authentication** shortcut, and **your recent activity**.

### Unsaved-changes save bar

- Editing a product (or other forms) now shows a sticky **"Unsaved changes —
  Save / Discard"** bar, and warns before you navigate away with unsaved edits.
  **⌘S / Ctrl+S** saves. Previously the bar only worked on a full page load;
  now it works when you open a form from the sidebar too.

### Skip the setup checklist

- The **"Set up your store"** first-run checklist now has a **Skip** button, so
  stores that don't need it can hide it for good (you can still reach each step
  from Settings).

### Sidebar polish

- The left menu now has **uniform row heights and spacing**, a **consistent
  hover highlight and micro-animation across every item** (top-level, sections,
  and sub-items alike), and tighter **icon-to-label alignment**.

---

## v0.6.0 — 2026-07-11

### Pick your AI model from a permanent dropdown

- On the **Settings → AI** page, clicking **Fetch models** for a provider now
  **saves that model list**, so the "Pick from fetched models" dropdown is
  filled in every time you open the page — on any browser or device, not just
  the one you fetched from. Your currently-selected model is pre-highlighted.
- Previously the list was only remembered in the current browser and expired
  after a week; now it's stored with the provider, permanently.

---

## v0.5.2 — 2026-07-11

### Tidier left navigation

- Hovering an item in the left menu now looks the same everywhere. Sub-menu
  links (e.g. Categories, Collections under Products) used to only change
  text colour on hover while top-level items got a highlight — now every row
  gets the same subtle highlight.
- Even, consistent spacing between all navigation rows, and matching row
  heights so the hover highlight is uniform top to bottom.

---

## v0.5.1 — 2026-07-11

### Linda's tool-calling fixed (was failing on Anthropic)

- A provider mismatch made every AI action that used a tool fail with a
  cryptic *"All AI providers degraded"* error when the active provider was
  Claude (Anthropic) — and likely other strict providers. Internal tool
  names contained dots (`orders.update_status`), which those providers
  reject. Tool names are now sent in a provider-safe form, so Linda can run
  order updates, catalog edits, and every other tool again. If Linda felt
  "offline" despite a configured key, this was why.

### A calmer, sharper dashboard

- The dashboard now loads its intended typeface (Inter) everywhere — it was
  silently falling back to the system font, so text is crisper and more
  consistent across every page.
- KPI labels and table headers switched from ALL-CAPS to sentence case, and
  numeric columns align with even, tabular figures — easier to scan.
- One consistent focus outline on inputs, one accent colour across tabs,
  badges, and callouts (previously two slightly different blues), and several
  spots that ignored dark mode (status dots, "update available" tags, image
  "cover" labels) now theme correctly.

---

## v0.5.0 — 2026-07-10

### Search that spans the whole platform

- **Cmd/Ctrl + K** now opens a wide search across all of Morpheus OS. It finds
  **every dashboard page** (pulled live from the plugin registry, so new pages
  are searchable the moment they ship), plus live matches across **orders**
  (by number or customer email), **products** (name or SKU), **customers**,
  **categories**, **collections**, and **content pages** — grouped into tidy
  sections.
- Every search always offers a **"Search the shop for …"** action that jumps
  straight to the storefront results.

### A cleaner dashboard header

- Removed the redundant "Ask Linda" button from the header — Linda is always a
  keystroke away from the command bar.
- The account cluster (settings, notifications, your menu) now sits flush to
  the right edge.

### Easier AI provider setup

- Each AI provider now shows a **one-line description** in the "Add AI" picker
  so it's clear what each one is for (which are OpenAI-compatible, which run
  locally, relative cost/strengths).
- The **default model** field offers **curated model suggestions** as a
  dropdown, so you can pick a sensible model instantly — before you've even
  pasted a key. **DeepSeek** and **Hermes** are fully selectable.

### Reliability & security hardening (core)

A pass over the platform kernel fixed a batch of verified defects, each covered
by a new automated test:

- **Staff two-factor now fails *closed*.** If the second-factor check ever
  errored mid-sign-in, an enrolled staffer could previously slip through on the
  first factor alone — that gap is closed.
- **AI review panels are genuinely independent again** (a degraded provider no
  longer silently collapses several reviewers into one opinion).
- **Order status changes from the assistant** now follow the proper order
  lifecycle (and log each transition) instead of failing.
- Fixes to embeddings/semantic-search accuracy, AI provider failover, the
  DeepSeek/Hermes "configured" indicator, merchant email overrides, and the
  Packy provider endpoint.

---

## v0.4.4 — 2026-07-10

### A friendlier account menu

- The top-right account menu now shows **your name** instead of your email
  address (it falls back to email if you haven't set a name).
- Added **About Morpheus OS** and **Version & updates** shortcuts right in
  that menu, with the version you're running shown at a glance — one click
  to the full, explained changelog.

## v0.4.3 — 2026-07-10

### Consistent icons in the ad-channel dashboards

- The Google, Meta, TikTok, Pinterest, Microsoft, Snapchat and Reddit
  dashboards now use the same crisp icon set as the rest of the admin
  instead of emoji, so status markers render consistently everywhere.

## v0.4.2 — 2026-07-10

### Security hardening, order emails that actually send, and cleaner breadcrumbs

**Security**
- Closed four access holes: draft-order pages (including converting a draft
  into a real order), the promotions dashboard, a payment-intent lookup, and
  the agent GraphQL endpoint were reachable more broadly than intended —
  all now properly staff-/owner-scoped. Newsletter signup and support chat
  got rate limits.

**Order notifications that were silently broken**
- The **"your order shipped"** and **order-cancelled** emails, the
  **stock-reservation release on cancel**, and the **refund confirmation /
  affiliate clawback** all had templates and handlers but were never actually
  triggered — the underlying events weren't firing. They fire now, so those
  emails and side-effects work for the first time. (Reminder: there's still
  no dedicated "shipped with tracking" email — tracked as a follow-up.)

**Dashboard breadcrumbs**
- Breadcrumbs now follow where a page sits in the sidebar (e.g.
  "Dashboard › Multivendor › Vendors") instead of exposing internal routing
  ("Dashboard › Apps › Marketplace › Vendors").

**Under the hood**
- Restored the security-lint CI gate, fixed a flaky test, pinned a
  previously-transitive dependency, removed three unused ones, and
  de-branded a few generic-layer defaults so the platform reads neutrally
  for non-dot-books operators. Full suite 2,016 tests green.

## v0.4.1 — 2026-07-10

### Shipping rates now actually show at checkout, plus a deep decoupling pass

- **Fixed: configured shipping rates never appeared at checkout.** A broken
  internal call meant every checkout silently fell back to free "Standard
  delivery" regardless of the zones and rates you set up. Your configured
  rates (including live carrier quotes) now show; stores without matching
  zones keep the free-standard fallback.
- **Cleaner module boundaries across the platform** (invisible today,
  faster and safer changes tomorrow): checkout's payment picker, search
  ranking, "you might also like", per-visitor product ordering, the GDPR
  data export/erasure, and the login cart hand-off all flow through the
  platform event bus — so disabling a module now genuinely removes its
  behaviour everywhere.
- **One feed engine for all ad channels** — Google, Meta, Pinterest,
  Snapchat, TikTok and Microsoft product feeds now share a single
  resolver (verified byte-identical output), so feed fixes land once,
  for every channel.
- 28 new tests; full suite 2,008 green.

## v0.4.0 — 2026-07-10

### PayPal, a merchandising brain for every shelf, and a platform-wide quality pass

**Payments**

- **PayPal** — shoppers can now pay with PayPal at checkout. Enable it in
  Settings → Payments with your client ID + secret; checkout redirects to
  PayPal for approval and returns to the order confirmation. Refunds issued
  from the dashboard flow back through PayPal automatically, and webhooks
  keep order status in sync.
- **Apple Pay readiness** — the storefront now serves the Apple Pay domain
  verification file automatically, so enabling Apple Pay in Stripe "just
  works" with no file uploads.

**Dynamic merchandising (the Dynamics app, rebuilt)**

- **Take control of any shelf** — Dynamics can now control every product
  placeholder in the store (home hero, "New & notable", staff picks,
  product-list ordering, category & collection pages, page-builder
  sections) — not just its own carousels. One click per surface in
  Dashboard → Dynamics; disable the plugin and every surface reverts to
  the theme default.
- **Smart strategy** — a transparent AI blend of purchase probability
  (from your own analytics), 7-day trend, what the shopper is browsing
  right now, and freshness — with a guaranteed exploration slot so new
  products always get seen.
- **"Why is this product here?"** — every block has a live preview showing
  each product's score broken into bars (probability / trend / session /
  recency) plus Pinned and Exploring badges, and autopilot blocks can be
  previewed as any visitor segment.
- The announcement strip above the home hero is gone — the hero breathes.

**Quality & trust (platform-wide audit)**

- **Secrets are now write-only everywhere** — 14 settings fields (AI
  provider keys, Stripe secrets, Turnstile, ElevenLabs) no longer echo
  stored values back into the settings form.
- **Dashboard forms tell the truth** — invalid saves over AJAX (variants,
  coupons, customers, addresses, password) now surface the validation
  errors instead of a false "Saved".
- **Accessibility** — the home hero carousel dots meet WCAG 2.2 touch-target
  size and the shop filters are screen-reader labelled; the axe gate is
  green again.
- Under the hood: the full test suite (1,990 tests) and every CI gate is
  green; money amounts from carriers/GraphQL are precision-safe; duplicated
  helpers consolidated; 9 dead templates removed; the remaining
  architecture debt is mapped in `docs/plans/boundary-debt-2026-07.md`.

## v0.3.0 — 2026-07-10

### The analytics & intelligence wave — see what your store already knows

- **NPS dashboard** (Post-purchase → NPS) — the surveys you were already
  collecting finally add up: overall NPS with promoter/passive/detractor mix,
  response rate, a 12-week trend, per-product scores, and a recent-detractors
  feed so you can follow up while it still matters.
- **Subscription analytics** — committed MRR, recognized-MRR trend from paid
  invoices, churn rate, the trial→paid funnel, and a per-plan breakdown.
- **Customer segments (RFM)** — every customer is scored nightly on recency,
  frequency and monetary value and placed in a named segment (champions, loyal,
  at-risk, lost, new, potential). Segment changes fire an event your workflows
  can react to — e.g. a win-back campaign when someone slips to *at-risk*.
- **Marketing attribution & ROAS** — order revenue is split across the
  channels that touched the customer's journey under five attribution models
  (last-touch, first-touch, linear, time-decay, position-based), and combined
  with ad spend pulled from your connected Meta and Google accounts into a
  per-channel ROAS view.
- **Funnel drop-offs** — the conversion funnel now shows exactly where people
  leave (step-to-step drop-off table) and how this period compares to the last.
- **Overstock detection** — the stockout forecaster now also flags slow-moving
  and dead stock (90+ days of cover), lists it on the forecast page, and fires
  an event that can trigger a markdown or promo workflow.

### New app: Feature adoption
- An install-health score (0–100) on your dashboard home, plus an adoption
  matrix showing which of your installed apps are actually used (7/30/90 days)
  and which haven't been touched in 90 days — deprecation candidates. Tracking
  is aggregate-only: no per-event rows, no personal data.

### New app: Live commerce
- Schedule **live shopping events**: an embedded stream (YouTube Live or any
  HLS embed) with pinned, buyable products. Your storefront gets `/live/` and
  a per-event page that flips to a replay when you add a recording; the home
  page teases the next event automatically. Sales from an event are attributed
  through the new attribution pipeline.

## v0.2.28 — 2026-07-08

### New: an About page for your platform
- **Settings → About Morpheus** explains what Morpheus is, its three surfaces
  (storefront, dashboard, and Linda), and lists **every app installed on your
  store** — read live from the plugin registry, each with its version and on/off
  state. One clear map of everything running.

### A smoother, more consistent dashboard
- **Breadcrumbs are fixed** across the whole dashboard — pages that used to show
  the trail twice now show it once, and several edit screens gained proper page
  titles.
- **Dark-mode fixes** — the self-improvement and cohort-retention pages no longer
  render with light panels in dark mode; several tables and status badges moved to
  the standard styling.
- **Micro-animations** — dashboard cards and tiles ease in, tabs give hover
  feedback, and success moments get a subtle pop. All motion respects your
  operating system's "reduce motion" setting.
- Fixed a crash on the New / Edit workflow page.

### Storefront
- **Full-width layout** — the browse pages (home, shop, categories, search, and
  product pages) now stretch to fill the screen, and the book grid adds more
  columns on wide displays instead of enlarging the covers. Checkout and cart stay
  comfortably bounded for readability.
- Removed an empty **"Pairs with this"** section that could appear on product
  pages with nothing listed under it.

## v0.2.27 — 2026-07-03

### Linda learns (self-learning Release 1)
- **Memory recall is now semantic and question-aware.** Linda ranks her
  remembered facts against what you're asking *right now* — "where do my
  parcels leave from" surfaces "warehouse is in Berlin" even though they share
  no words. (Previously recall was recency-only, and the memory block was
  injected twice per turn — fixed, halving the token overhead.)
- **Linda now learns from her background Workers.** When a delegated job
  finishes, a short reflection pass judges the outcome, saves up to two
  durable lessons to her memory, and records the verdict on any learned skill
  the job used. A skill that keeps failing retires itself — and Linda
  remembers why, so she can tell you.
- **Tool gaps are tracked.** When a Worker clearly lacked a capability, the
  gap is remembered (`tool_gap.*`) — groundwork for Linda proposing her own
  new tools (propose-only, owner-approved) in an upcoming release.

### Linda's morning briefing (self-learning Release 2, opt-in)
- **Linda now works before you do.** Turn on Settings → General → *Linda's
  daily briefing* and every morning (06:00 UTC) a read-only agent reviews
  your last 24 hours — sales, errors, stock, reviews — and posts a short
  briefing on the dashboard home with up to three suggested actions. Each
  action is an "ask Linda" button that pre-fills the chat; nothing is ever
  executed without you. Distinct from Linda's Pulse (rule-based alert
  cards): the briefing is an open-ended, tool-grounded review.

### Linda writes her own tools — you hold the pen (self-learning Release 3)
- **Proposals queue.** Linda → Proposals (superuser only) lists every tool
  Linda drafted for herself: the source, the static safety scan, and the
  multi-model consensus verdicts side by side, with Approve / Reject / Run
  consensus review. Nothing executes and nothing touches the repo from
  drafting; approving records your decision, and code is only written — to
  a git branch, never main — when `MORPHEUS_SELF_UPDATE_ENABLED` is also
  set. Every decision is audited.
- **The flywheel.** Weekly, Linda turns capability gaps her Workers hit
  twice or more into drafted proposals in that queue — the platform now
  notices what it's missing and proposes the fix itself.
- **Evals harness.** `manage.py run_assistant_evals` scores Linda against
  20 golden tasks (tool grounding, write-gate discipline, no invented
  numbers), so every assistant change is measured against a baseline.

---

## v0.2.26 — 2026-07-02

### Privacy
- **GDPR/ePrivacy is now a single switch.** Settings → General → *GDPR / ePrivacy
  features* turns the compliance surfaces on or off in one place. When off (for
  stores outside GDPR jurisdiction — US-only, B2B), the cookie-consent banner is
  suppressed and the self-service data-export / account-erasure pages are
  disabled. Default **on**, so existing stores are unchanged.

---

## v0.2.25 — 2026-07-02

### Agent governance (enterprise Phase 1 — ADR 0027)
- **Protected agent tools now require explicit approval.** Tools that make
  sensitive writes (refunds, pricing, roles, translations…) can no longer be
  executed over the MCP admin API just because a token has the right *scope* —
  the merchant must grant that specific tool to that specific token under
  **Settings → Developer → MCP tokens → Approved protected tools**. Ungranted
  calls are refused. *(Tightening: an existing token that could previously fire
  a protected write now needs the tool ticked once.)*
- **Every agent action is audited.** Each executed MCP tool call, and every
  refusal, now writes to the core audit trail (who / what / arguments / result /
  duration) — the automated write surface is no longer invisible.
- **Per-token rate limits.** Each token has a tool-call budget per minute
  (default 120, adjustable), so a runaway or hostile agent can't exhaust the
  platform.
- **Agent order attribution now works.** When a verified shopping agent places
  an order, its id is recorded on the order (`order.metadata.agent_id`) — the
  manifest advertised this, but it was never actually wired until now.

---

## v0.2.24 — 2026-07-02

### Storefront
- **Letterpress decode, refined.** Hero titles and descriptions now animate as
  individual letters: each character "searches" in muted accent ink, then locks
  into place with a tiny settle pop — like type slugs snapping into a composing
  stick. Words wrap as units, so lines never break mid-word during the effect.
- **The hero headline is dynamic too** — it decodes once on page load. The old
  explainer paragraph under it (which described the widget rather than the
  books) is removed for a cleaner, more confident opening.
- **Friendlier micro-details.** Primary buttons lift gently on hover, and text
  selection uses the house ink-on-paper colors. All motion still honors
  `prefers-reduced-motion`.

---

## v0.2.23 — 2026-07-02

### Reliability & supply chain (enterprise Phase 0)
- **20 plugins' tests now actually run in CI.** They were pytest-style suites the
  Django test runner silently reported as "Ran 0 tests" — checkout_experience,
  subscriptions_plus, returns_portal, referrals and 16 more. A new CI step runs
  them (all 30 pass), and its glob auto-covers future plugins so the
  silently-never-run class can't recur.
- **Dependency CVE gate is now enforcing.** `pip-audit` was report-only; triaged
  clean (zero known CVEs), so any finding now blocks the merge.
- **Hash-pinned lockfile.** Dependencies floated on `>=` ranges; CI now installs
  from `requirements.lock.txt` (universal, `--require-hashes`), so CI tests the
  exact versions that would ship.
- **Webhook deliveries are idempotent.** A broker redelivery (worker
  crash/timeout after the POST) re-ran the delivery and double-POSTed the
  receiver; an already-delivered row is now skipped.

## v0.2.22 — 2026-07-02

### Storefront
- **Hero titles + descriptions "decode" on each slide.** As the home hero
  rotates through featured books, each book's title and description animate
  letter-by-letter — every character rapidly cycles through glyphs then locks
  into place (a "finding the right letter" reveal), including on first load.
  Framework-free (matches the vanilla dot_books theme), respects
  `prefers-reduced-motion` (settles instantly), is layout-contained (no shift),
  and never exposes the transient scramble to screen readers.

---

## v0.2.21 — 2026-07-02

### Observability (error logging is now one core system — ADR 0025)
- **All errors land in one place.** Celery task failures, REST + GraphQL API
  errors, and captured log records were being written to a *separate, simpler*
  `ErrorEvent` table in the observability plugin — invisible to the core error
  dashboard, the fingerprint dedup, and the self-improvement loop. They now all
  record into the core `core/errors` system, so every error is fingerprinted,
  deduped, request-correlated, and visible in one dashboard.
- **Three core→plugin boundary violations removed** (`core/brain/log_handler.py`,
  the Celery handler, and the assistant's `logs.*` tools no longer import a
  plugin for errors — boundary baseline 24 → 22). API errors now capture the
  real request (path/user/request_id) too.
- **Linda's log tools** (`logs.recent_errors`, `logs.search`) now read the
  unified core error log instead of the frozen plugin table, and surface the
  richer fields (exception class, level).
- New `core.errors.record_message()` for callers that only have a formatted
  string (no live exception). The plugin's `record_error` is now a thin
  forwarding shim into core. (Retiring the plugin's parallel table is a
  follow-up data migration.)

---

## v0.2.20 — 2026-07-02

### Reliability (enterprise-readiness Phase 1)
- **Domain events are delivered again.** The transactional-outbox publisher
  (`process_outbox`) existed but was scheduled on no Celery beat, so events
  written to the outbox accumulated undelivered and the at-least-once guarantee
  was silently broken. It now runs every minute.
- **Bounded retry on publish failure.** A transient NATS failure now keeps the
  event `PENDING` and retries on the next drain (new `attempts` counter),
  dead-lettering to `FAILED` only after 5 attempts — previously the first
  failure stranded the event permanently.

### CI hardening
- `manage.py check --deploy` is now an **enforcing** gate at ERROR level
  (was a no-op `--fail-level WARNING || true`).
- `mypy` (already configured, never run) now produces a **non-blocking baseline
  report** over the `core/` kernel in CI.

---

## v0.2.19 — 2026-07-01

### Dashboard UI
- **Help "?" tooltips now actually work.** The `context-help` component had no
  styling, so field help text rendered inline (cluttering the page). It's now a
  small **?** that reveals its text in a tidy tooltip on **hover, keyboard
  focus, or click/tap** — applied everywhere the "?" already appears (settings,
  products, orders, home, AI providers…).
- **Wider, standardised page width.** The dashboard content area was capped at
  1280px and most pages re-capped themselves *narrower* still (settings at
  896px, order detail at 1024px), leaving big empty margins. The global cap is
  now 1536px (`max-w-screen-2xl`) and the working pages (home, lists, settings,
  analytics, product/order detail) drop their own caps to fill it — one
  consistent width. Focused single-action forms (refund, fulfil, address, new
  order) intentionally stay narrow for readability.

---

## v0.2.18 — 2026-07-01

### Plugins / modularity (ADR 0023)
- **Disabling a plugin now reliably removes its dashboard/storefront surfaces.**
  Fixed a class of bug where a disabled plugin's contributed cards, KPIs, and
  feed items could keep rendering: the hook bus now skips any handler owned by a
  disabled plugin (previously `deactivate()` left `ready()`-wired hooks in
  place, so they kept firing). This makes **every** `register_hook`-based
  contribution disable-safe at once.
- **Book Product's "Book details" card** on the product editor was hard-wired
  into the dashboard (so it showed even when book_product was disabled). It now
  contributes through the `PRODUCT_FORM_CARDS` / `PRODUCT_FORM_SAVED` hooks like
  every other product-form card, so it appears only while the plugin is enabled.

---

## v0.2.17 — 2026-07-01

### Assistant
- **Linda's per-page helper is now dismissible per page.** The card's control is
  a **✕** that hides Linda *on that specific page* — it stays gone there on
  reload, but still appears on pages you haven't dismissed (replacing the old
  global Hide/Show toggle). Dismissing a page also skips its AI call entirely.
  The master on/off switch remains **Settings → General → AI-assisted tips &
  help** (`ai_page_help`).

---

## v0.2.16 — 2026-07-01

### Localization
- **Multi-language storefront URLs (opt-in).** The storefront can now serve each
  language on its own URL: the **core language** (Settings → General) stays at
  the root (`/product`), every other enabled language gets a prefix (`/fr/…`,
  `/sr/…`), with `reverse()` keeping the prefix as visitors browse. A **language
  switcher** appears in the footer once more than one language is enabled.
  Enable languages per environment with `MORPHEUS_LANGUAGES="en,fr,sr"` (default
  is the core language alone — no change until you opt in). Dashboard + API stay
  unprefixed. Per-language `hreflang` is the next step.

---

## v0.2.15 — 2026-07-01

### Localization
- **Translations are now a programmable API** — external translators and
  translation tools can read/write translations over **MCP and GraphQL**, not
  just the dashboard. New scopes `i18n.read` / `i18n.write` gate the access.
  - MCP tools: `i18n.languages`, `i18n.get_translations`, `i18n.set_translation`
    (any object, addressed by `content_type` + `object_id`).
  - GraphQL: `enabledLanguages`, `translations(...)` queries + a
    `setTranslation(...)` mutation. The same bearer token works from either.

---

## v0.2.14 — 2026-07-01

### SEO
- **Category & collection pages now advertise a price range** in their
  structured data (schema.org `AggregateOffer` — e.g. "from $5–$30, 240 items").
  Google and AI Overviews reward this on listing pages, improving how
  categories surface in rich results and AI answers. Builds on the existing
  `CollectionPage`/`ItemList` JSON-LD; a reusable `aggregate_offer()` helper is
  available for variant ProductGroups next.

---

## v0.2.13 — 2026-06-30

### Updates
- **Crash-safe one-click update.** The **Settings → Updates** page now always
  shows an **Update now** button when a version is available. Applying is
  hardened against bad updates: it **backs up**, then **boot-probes the new
  code in a fresh process before migrating** (so a non-bootable update reverts
  with the database untouched), and **refuses updates that change dependencies**
  (those need an image rebuild — avoids the "imports a package that isn't
  installed" crash). Any failure auto-rolls-back to the prior version.

---

## v0.2.12 — 2026-06-30

### Updates
- **Automatic "update available" check.** Morpheus now checks the upstream repo
  once a day and, when a newer version is available, surfaces an **Update
  available** item in the dashboard activity feed linking to **Settings →
  Updates** — so you know to update without manually checking. The check is
  cached (no per-page network cost) and fails silently if git/network is
  unavailable. Applying updates stays opt-in (`MORPHEUS_SELF_UPDATE_ENABLED`)
  and CLI/dashboard-driven as before.

---

## v0.2.11 — 2026-06-30

### AI providers
- **AI providers panel is now a connection manager.** Instead of one long form
  listing every possible provider, the panel shows **only the providers you've
  connected**. An **"Add AI"** button opens a picker of the remaining provider
  templates; connect one and it joins the list (and leaves the picker). Each
  connected provider can be **disconnected** — clearing its key and, if it was
  the active provider, reassigning the active one automatically.
- **DeepSeek is now a supported provider** (OpenAI-compatible; `deepseek-chat` /
  `deepseek-reasoner`). Connect it under Settings → AI providers.
- **Fixed: selecting apikey.fun reported "No AI provider selected."** apikey.fun
  was offered in settings but had no provider implementation; it now resolves
  and runs like any other provider.

### Dashboard
- **Icon set reverted to Remix Icon** for a consistent line-weight look across
  the dashboard.
- **Per-page Linda helper** — when *AI-assisted tips & help* is enabled
  (Settings), Linda explains each dashboard page and advises what to do next.

### Performance
- The active storefront channel is now resolved once per request, removing a
  duplicate lookup that ran on every page.

---

## v0.2.10 — 2026-06-28

### Morpheus Brain
- **New "Advisory" tab — a long-form AI briefing on your whole site.** Beyond the
  short prioritized recommendation list, the Brain now writes a comprehensive,
  readable advisory in prose: what's healthy, what needs attention, and the
  concrete improvements, patches and changes to make next — grounded in the live
  platform signals (errors, code quality, SEO/content, storefront performance,
  plugin health). It regenerates automatically once a day and on demand via
  **Regenerate briefing**, and degrades cleanly to a prompt when no AI provider
  is configured.

### Dashboard
- **Seamless navigation.** Moving between dashboard pages no longer flashes —
  the sidebar now does an in-place content swap (with a quick, intentional
  cross-fade) instead of a full reload, and a double-animation flicker on every
  page change was removed. Respects "reduce motion".

### Storefront
- **Nicer browse tiles.** The Genres / Topics / Authors index tiles got a visual
  pass — clearer hover, an affordance arrow, designed placeholders, focus rings.

### Fixes & hardening
- AI "Ask Linda" buttons now HTML-escape their values (defense-in-depth); a
  dashboard settings-load failure is now logged instead of silently masked; the
  nav cart-count is resolved in one query instead of two; and a book-product save
  error now surfaces in logs instead of being dropped under a false "Saved".

### Developer
- **Architecture guard-rails.** CI now blocks any *new* wrong-direction
  `core/ → plugins.installed` import (baseline-and-ratchet, so the debt can only
  shrink) and runs the plugin disable-test as its own gate.

## v0.2.9 — 2026-06-28

### Fixes
- **Restored the staff dashboard.** A recent change used the `get_guided_ux_mode`
  template tag in the dashboard base template without loading its library, which
  could 500 every dashboard page. Now loads `morph_dashboard`.
- **Added missing migrations** for the analytics-tracking, guided-UX, and
  dynamic-products grid models that had shipped without them (additive only —
  new columns/tables), so those features work in production and the migration
  gate is green again.
- **AI provider API keys are now write-only in settings.** The provider key shows
  as `********` and a blank/unchanged submit preserves the stored key instead of
  overwriting it — previously, saving AI settings without re-typing the key would
  have wiped it.

## v0.2.8 — 2026-06-25

### Security
- **Staff SSO (SAML 2.0 + OIDC), OFF by default.** New `staff_sso` plugin lets
  staff sign in through your identity provider (Okta, Entra/Azure AD, Google
  Workspace) via **OIDC** or **SAML**, configured at **Settings → Developer →
  Staff SSO** (issuer/client or IdP metadata, plus an email-domain allowlist and
  optional group claim). First sign-in just-in-time provisions the staff account;
  a "Sign in with SSO" button appears on the staff login page once configured.
  Crucially, **SSO does not bypass MFA** — an enrolled staffer is still required
  to pass their authenticator code, whether they came in by email-OTP, OIDC, or
  SAML. SAML assertions must be signed. Email-OTP stays as the break-glass path;
  disabling the plugin reverts sign-in to email-OTP exactly.
- **Fixed: dashboard settings panels echoed stored secrets in clear text.** The
  shared settings renderer ignored password fields, so saved secrets (API keys,
  the new SSO client secret, etc.) were rendered into the page as readable values.
  Secret fields are now **write-only** — masked, never pre-filled, and a blank
  submit preserves the stored value. Applies to every plugin's settings panel.

### Storefront
- **Admin "Edit" button on the storefront.** When you're signed in as staff, the
  top admin bar now shows an **Edit** link that deep-links to the dashboard editor
  for whatever you're viewing — product, **category** (a new category edit page),
  **collection**, **genre**, **topic**, or **CMS page**. Customers see nothing.

> **Operator note:** this release adds two native Python dependencies
> (`pyjwt[crypto]` for OIDC, `python3-saml`/`xmlsec` for SAML). They ship as
> prebuilt wheels, but the deploy image must reinstall `requirements.txt` on this
> release. Both SSO providers are inert until an IdP is configured.

---

## v0.2.7 — 2026-06-24

### Security
- **Staff two-factor authentication (MFA).** New `staff_mfa` plugin adds a TOTP
  second factor (authenticator apps — Google Authenticator, 1Password, Authy)
  on top of the existing email sign-in code for staff accounts. Self-service
  enrollment lives at **Settings → Two-factor authentication** (scan a QR,
  confirm a code, save one-time recovery codes). Lost your device? A recovery
  code gets you in; an admin can run `python manage.py reset_mfa <email>` as a
  break-glass (audited). **Enrolled** staff are always challenged at sign-in.
  Enforcement for *un*enrolled staff is **opt-in**: turn on **Require MFA for all
  staff** in **Settings → Developer → Staff two-factor** to prompt them to enroll
  at sign-in (a first-admin grace prevents locking the org out before anyone has
  enrolled; hard per-page gating lands in a follow-up). Email-OTP stays factor
  one and is unchanged; disabling the plugin reverts sign-in to single-factor
  exactly. Customers are unaffected.

### Agentic commerce
- **ACP (Agentic Commerce Protocol) — Phase 1, OFF by default.** New
  `agentic_checkout` plugin lets AI shopping agents discover products and build a
  checkout session against the platform — a discovery manifest at
  `/.well-known/acp.json`, an ACP product feed, and the `checkout_sessions`
  create/read/update/cancel endpoints (Bearer-scoped via `acp.checkout`), backed
  by the existing cart. Conformant to the real ACP `2026-04-17` spec. The payment
  path (Stripe Shared Payment Token) is **Phase 2** and intentionally returns
  "unsupported" until a merchant enrols — so nothing charges yet. Ships disabled;
  enable from Dashboard → Apps.

### Plugins
- **Abandoned-cart recovery is now one consent-checked drip — and the
  double-send is fixed.** Previously *two* recovery emails went out per abandoned
  cart (a core handler and a marketing task both fired). Consolidated into a
  single multi-step sequence owned by the `cart_abandonment` plugin: configurable
  send delays (default 1h / 24h / 72h), merchant-editable templates
  (**Settings → Notifications**), a marketing-consent check, and a guard that
  stops once the cart converts. Disabling the plugin now removes recovery email
  entirely.

### Fixes
- **Loyalty points no longer accrue to guest checkouts** (the guard compared
  against the wrong default, so guest orders could mint points with no account to
  hold them).
- **Digital downloads can't exceed their limit under a race** — the
  download-count claim is now atomic, closing a window where a rapid double-click
  could grant an extra download.
- **Webhooks dispatch only after the transaction commits** (and are suppressed on
  rollback), so a subscriber never sees an event for a change that didn't land.

### Developer
- **Supply-chain scanning:** weekly Dependabot PRs (grouped) plus a `pip-audit`
  CVE check in CI (advisory).

---

## v0.2.6 — 2026-06-21

### Plugins
- **Linda now reports the real product count.** Her `products.search` tool
  returned `count = page size` (capped at 20–50), so she'd say "there are ~40
  books" for an 859-product catalogue. It now returns `total` (the true number
  of matching products) alongside the sample, and a new **`products.count`** tool
  answers "how many products/books" exactly. Linda's prompt points at it.
- Retired the PDP **"Pairs with this / Goes well together"** recommendation block
  (cropped book covers; only rendered for the few products with co-purchase
  data). The recommendation service stays available for reuse.

---

## v0.2.5 — 2026-06-21

### Core
- **Morpheus Brain now actually sees application errors.** A fail-soft, loop-safe
  logging handler routes ERROR-level app logs into the error pipeline
  (`ErrorEvent` → error_log collector → `SiSignal`), so the Brain's **Errors tab**
  and AI analysis reflect real exceptions — completing the "analyze error logs"
  capability (previously those logs only hit the console).
- **Brain correctness fixes:** merchant insights are now fed to the AI digest
  (they were gathered + shown but never sent to the model); a transient AI-provider
  failure no longer pins a stale error banner for 24h (only successful analyses are
  cached); and the signal snapshot is cached ~90s (was ~18 DB queries on every page
  load), refreshed on demand when you click *Refresh analysis*.

---

## v0.2.4 — 2026-06-21

### Core
- **Fixed: CSP violation flood (~2,500/day).** The storefront Content-Security-
  Policy (report-only) didn't allow `cdn.ampproject.org`, which the webstories
  plugin's `<amp-story-player>` PDP embed loads (amp-story-player + amp-loader +
  v0). Added it to `script-src`/`style-src`, silencing the reports. (Report-only,
  so nothing was broken — just noise the self-improvement engine kept flagging.)
- **Fixed: false plugin-validation error on every boot.** `validate()` checked a
  plugin's `requires` only against other plugin names, so a `core.*` dependency
  (e.g. `ai_stylist` → `core.audit`) wrongly logged "not installed" even though
  the core app is always present. `core.*` deps now resolve against
  `INSTALLED_APPS`; the `ai_stylist`/`core.audit` boot error is gone.

---

## v0.2.3 — 2026-06-21

### Plugins
- **Fixed:** the *Version & updates* page rendered blank in production — it
  depended on a markdown library that isn't installed there. Replaced with a
  small built-in renderer (no external dependency), so the release notes now
  show. (If this page was empty for you, that's why.)
- Settings nav: **Morpheus Brain** and **Version & updates** are now pinned
  right under **General** instead of buried at the bottom of the settings list.

---

## v0.2.2 — 2026-06-21

### Core
- Plugin contract gains `enabled_by_default` — a plugin can ship
  **installed-but-OFF**, opting in from Dashboard → Apps (default stays on, so
  existing plugins are unchanged).

### Plugins
- **Booking marketplace** (new, **off by default**): a multivendor *services*
  marketplace alongside the product one. Vendors offer time-slot
  `BookableService`s with weekly availability; customers book a slot at
  `/bookings/`. Manage at Dashboard → Bookings. Enable it from Dashboard → Apps.

---

## v0.2.1 — 2026-06-21

### Storefront
- Author page: the author image now spans the full content width instead of a
  cramped 160px thumbnail.

---

## v0.2.0 — 2026-06-20

### Core
- **Morpheus Brain** is now a **core capability** (`core/brain/`), not an app —
  always on (the surface plugin is protected from disable). It continuously
  reads the platform's own signals (code-quality + error-log findings from the
  self-improvement immune system, plugin health, SEO/content audits, storefront
  Core Web Vitals) and uses your **configured AI provider** to synthesize a
  prioritized list of fixes, improvements, and feature ideas. Refreshes on a
  6-hour beat and on demand; degrades cleanly when no AI is configured.
- **More comprehensive error/warning logging** — `django.request`,
  `django.security`, `django.db.backends`, `celery`, and Python `warnings` now
  flow through the log stream the error-log collector + Brain read.

### Plugins
- **Morpheus Brain** surface (Settings → Morpheus Brain): tabbed console for the
  above (Overview, Plugins, Code, Errors, Content & SEO, Storefront,
  Improvements) with a one-click **Refresh analysis**.

---

## v0.1.0 — 2026-06-20

The current foundation release. Highlights since the platform came together:

### SEO & structured data (rich results)
- **One complete, valid Product** rich result per product page — offer with
  price, availability, shipping, return policy, `itemCondition`, and
  `priceValidUntil`, plus absolute `image`, `brand`, and review stars
  (`aggregateRating` + `review`) when reviews exist.
- **Google Book structured data** — Work → Edition → ReadAction, with `sameAs`
  (Open Library) + OCLC identifier so public-domain titles are reconcilable
  without fabricated ISBNs.
- **VideoObject** for product videos, and an enriched **Organization** graph
  (contact point + postal address) for the brand knowledge panel.
- **Rich-snippets editor** gained Book + enriched Article types.
- Fixed the AMP Web Story canonical error (stories are now standalone /
  self-canonical).

### Catalog & books
- **Identifier fields** (ISBN-13 / OCLC / Open Library work ID) on the product
  edit form, plus a bulk `backfill_book_identifiers` command that reconciles the
  catalog against Open Library with conservative title+author matching.

### Storefront
- Editorial homepage hero, bigger grid titles with first-sentence excerpts.

### Platform
- **Version & updates** page in Settings (this page), backed by this document.
- **Morpheus Brain** (Settings → Morpheus Brain) — a tabbed intelligence console
  that aggregates plugin health, code analysis & self-improvement, content &
  SEO, storefront Core Web Vitals, and improvement recommendations, read-only
  from the platform's own engines.
- **Book identifiers** — ISBN-13 / OCLC / Open Library fields on the product
  form, plus the `backfill_book_identifiers` bulk reconciliation command.

_Earlier engineering history (PR-level) lives in [`CHANGELOG.md`](../CHANGELOG.md)._
