# Morpheus OS — Release Notes

Detailed, user-facing updates to the **Morpheus OS core** and its modules,
surfaced in **Dashboard → Settings → Version & updates**.

> **House rule (enforced):** every Morpheus OS version bump MUST add a dated,
> versioned `## vX.Y.Z — YYYY-MM-DD` entry here describing the change. This file
> is the single source of truth for the in-dashboard changelog. See
> [`CLAUDE.md`](../CLAUDE.md) and the torsor ADR "Versioned release notes".

---

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
