# Competitive Edge Buildout — Implementation Plan (2026-07)

> **For agentic workers:** execute task-by-task with the verify step after every task.
> Source: the 2026-07-10 competitive gap analysis (chat), grounded against the tree
> at v0.3.0 (107 plugins). Follows the format of
> [`analytics-intelligence-2026-07.md`](analytics-intelligence-2026-07.md), which
> shipped 9/9.

**Goal:** close the five gaps that block "beats every open-source platform" and
cash the "cutting-edge AI platform" claim: search → payments breadth →
per-visitor merchandising → AI support inbox → theme ecosystem.

**Ground truth (verified 2026-07-10 — corrections to the gap analysis):**

- `dynamics.calculate_grid_probabilities()` is **no longer a stub** — it's a real
  per-product weighted scorecard (intent/sales/demand/trend/quality ×
  inventory factor), nightly. What's missing is **per-visitor** scoring; the
  Autopilot phase builds on top of it, not instead of it.
- Payments already has a **gateway SPI**: `gateway_registry`,
  `services/routing.py` (validated picker, fail-soft default, slug recorded on
  `order.payment_gateway`), `PaymentGateway`/`PaymentGatewayConfig` models.
  Phase 2 = *implement providers on the existing SPI*, not design one.
- Search today is split three ways: storefront `/search` redirects keyword →
  PLP `icontains` facets; `mode=semantic` → catalog GraphQL `semanticSearch` →
  `ai_assistant/services/search.py` (embedding cosine in Python, Postgres FTS
  fallback). No typo tolerance, no suggest-as-you-type, no synonyms, no
  merchandising rules, no zero-result intelligence.
- `experiments` has a full engine (`services.results_for`, middleware
  assignment) with **zero UI and zero consumers** — Phase 3 gives it both.
- No helpdesk/support plugin exists. `themes/library/` contains only
  `dot_books`.

**House rules that bind every task below:** plugin-first (nothing in `core/`
except new hook constants), one concept = one model owner, cross-plugin via
`core.hooks` only, disable/delete litmus tests, migration per model, exact-value
unit tests for all math, `DATABASE_URL='sqlite:///:memory:'` for local tests,
ADR 0032 version bump per deploy, no new pip deps without justification.

---

## Phase 1 — P0: Search (new plugin `search`)

**Why first:** search is the #1 adoption veto and 30–40 % of revenue on content-
rich stores. Overlap audit: storefront owns the PLP UI, catalog owns product
data + GraphQL, ai_assistant owns embeddings. The new plugin owns **ranking,
suggestions, synonyms and search intelligence** — it *feeds* the existing PLP
via a filter hook rather than replacing it, so the PLP keeps working (plain
`icontains`) when the plugin is disabled.

### Task 1.1: Hybrid ranker + instant suggest

**Files:** create `plugins/installed/search/` — `apps.py`, `app.py`,
`ranking.py`, `views.py`, `urls_storefront.py`, `tests/`. Register in
`MORPHEUS_DEFAULT_APPS`. New hook in `core/hooks.py`:
`SEARCH_PRODUCT_IDS = 'search.product_ids'` (filter, value=`list[product_id]`,
kwargs: `query`, `limit`) — fired by the storefront PLP when `q=` is present;
no subscriber → PLP falls back to its current `icontains` path (disable-safe
for free).

- [ ] Failing tests first: exact-rank fixtures (title match beats description
      match beats trigram-only match; out-of-stock demoted not dropped), typo
      test (`harri potter` finds "Harry Potter" via trigram), sqlite fallback
      path returns sane results, suggest endpoint shape + latency budget.
- [ ] `ranking.py::rank(query, limit=60) -> list[product_id]`:
      1. Postgres: `SearchVector(name weight A, description weight B)` +
         `SearchRank`, OR'd with `pg_trgm` similarity > 0.3 for typo tolerance
         (enable the extension in the plugin's migration with
         `TrigramExtension()`; guard with `connection.vendor == 'postgresql'`).
      2. sqlite (tests/dev): `icontains` on name/description — same contract.
      3. Optional semantic rerank of the top 60 via the existing
         `ai_assistant` embedding service **through a lazy fail-soft import**
         (absent/disabled → skip; never a hard `requires`).
- [ ] Storefront PLP integration: in the PLP view's `q=` branch, replace the
      direct filter with the `SEARCH_PRODUCT_IDS` filter fire (subscriber
      registered in `app.py::ready()` via `register_hook`).
- [ ] `GET /search/suggest/?q=` (register_urls, JSON): top-8 products
      (id/name/slug/price/thumb) + top-3 categories, cached 60 s per query,
      rate-limited per IP. Storefront header search box gets
      debounced-fetch suggestions via a `StorefrontBlock(slot='global_head')`
      script — self-removes on disable.
- [ ] Verify: `DATABASE_URL='sqlite:///:memory:' python manage.py test
      plugins.installed.search plugins.installed.storefront` green; template
      compile; boundary guard clean. **Postgres-only paths must be tested in
      CI's `migrations`/Postgres job or explicitly marked skipped on sqlite.**
- [ ] Commit: `feat(search): hybrid keyword+trigram+semantic ranking with instant suggest (new plugin)`

### Task 1.2: Synonyms, merch rules, zero-result intelligence

**Files:** `search/models.py` + migration, `search/views_dashboard.py`,
`templates/search/dashboard.html`, `search/agent_tools.py`.

**Models (owner: search):**
```python
class SearchSynonym(models.Model):   # 'sci-fi' → 'science fiction' (two-way flag)
    term, expansion, two_way = CharField, CharField, BooleanField
class SearchRule(models.Model):      # pin/bury a product for a query prefix
    query_prefix, product FK('catalog.Product'), action ('pin'|'bury'), position
class SearchQueryDay(models.Model):  # aggregates only, mirrors FeatureUsageDay
    day, query (normalized), count, zero_results = DateField, CharField, PIntField, PIntField
    # unique_together: (day, query)
```
- [ ] Failing tests: synonym expansion changes ranking; pin forces position;
      SEARCH_PERFORMED subscriber increments `SearchQueryDay` (zero_results
      only when results_count==0); dashboard permission-boundary.
- [ ] Wire synonyms/rules into `ranking.rank()`; subscribe to the existing
      `SEARCH_PERFORMED` hook for the aggregate log (fail-soft).
- [ ] Dashboard page (`section='catalog'`): top queries, **zero-result report**
      (the money table — what shoppers wanted and didn't find), synonym + rule
      CRUD (dynamics form pattern).
- [ ] Agent tool `search.zero_result_report` + a Linda-proposable
      `search.add_synonym` (requires_approval=True) — "AI fixes its own
      zero-result queries" is the demo.
- [ ] Verify: suite green; disable litmus (suggest 404s, PLP falls back, nav
      gone); boundary guard.
- [ ] Commit: `feat(search): synonyms, pin/bury rules, zero-result intelligence + Linda synonym proposals`

### Phase 1 deploy gate
- [ ] MINOR bump + release notes → push → verify Coolify build → smoke:
      `/products/?q=<typo>` returns results, `/search/suggest/?q=` JSON, and
      the dashboard zero-result page.

---

## Phase 2 — P0: Payments breadth (owner: `payments`)

The SPI exists — these tasks add the two highest-veto providers **on it**.
Verified-Output rule applies: both SDKs (`paypal-server-sdk` or plain REST via
`requests`, already a dep) must be justified; prefer REST + `requests` (zero
new deps).

### Task 2.1: PayPal gateway

**Files:** `payments/services/paypal.py`, registration in the existing
`gateway_registry` bootstrap, settings-panel fields (client id +
`format: password` secret — write-only convention), `payments/tests/test_paypal.py`.

- [ ] Failing tests (contract-test against recorded REST fixtures, not
      hand-mocks of our own wrapper): create-order maps cart total/currency
      exactly; capture marks order paid via the same code path Stripe uses;
      refund routes back through `order.payment_gateway=='paypal'`; webhook
      signature verification rejects a tampered payload.
- [ ] `PayPalGateway` implementing the same surface `StripeGateway` exposes to
      `routing.py` (create intent/order → approval URL, capture on return,
      refund, webhook). Sandbox/live mode from config. Fail-soft: unconfigured
      → not in `enabled_gateways()` → picker never shows it.
- [ ] Webhook endpoint via `register_urls` + verification against PayPal's
      cert chain; reuse the existing order-paid hook flow so
      fulfillment/notifications fire identically to Stripe.
- [ ] Verify: `…test plugins.installed.payments` green (existing Stripe tests
      untouched); checkout picker shows PayPal only when configured.
- [ ] Commit: `feat(payments): PayPal gateway on the existing SPI — orders, capture, refunds, webhooks`

### Task 2.2: Wallets + BNPL through Stripe (cheapest 80 %)

Apple Pay / Google Pay / Klarna / Afterpay all ship as **Stripe payment-method
types** — no new provider integration, just Payment Element configuration.

- [ ] Failing tests: payment-intent creation passes
      `automatic_payment_methods` (or the configured method-type list);
      settings toggle round-trips; unconfigured → unchanged legacy behaviour.
- [ ] Switch the Stripe intent to `automatic_payment_methods={'enabled': True}`
      + render the Payment Element variant in `checkout_experience`'s payment
      step (its own template, plugin-owned); merchant toggles per-method in the
      payments settings panel.
- [ ] Apple Pay domain-association file served via `register_urls`
      (`/.well-known/apple-developer-merchantid-domain-association`).
- [ ] Verify: payments + checkout_experience suites green; manual smoke on
      Stripe test mode (wallet buttons render when enabled).
- [ ] Commit: `feat(payments): wallets + BNPL (Apple/Google Pay, Klarna, Afterpay) via Stripe Payment Element`

### Phase 2 deploy gate
- [ ] MINOR bump + release notes → push → **manual live smoke of checkout with
      Stripe test keys before announcing** (money path).

---

## Phase 3 — P1: Merchandising Autopilot (new plugin `smart_merchandising`)

The AI flagship. Per-visitor reranking measured by the dormant `experiments`
engine. Builds ON the shipped per-product scorecard (dynamics) — this plugin
adds the **visitor** dimension and the **learning loop**. Design per the
research in the parked plan (`~/.claude/plans/` Track 2): serve-time scorecard +
Thompson sampling, no ML deps, no request-path model inference.

`requires = ['experiments', 'analytics', 'personalisation']` (their hooks/data
contracts, not their models — all reads via hooks or their public services).

### Task 3.1: Visitor features + bandit reranker

**Files:** create `plugins/installed/smart_merchandising/` — `apps.py`,
`app.py`, `features.py`, `reranker.py`, `models.py` (`RankerArmStat`:
arm/slot, impressions, conversions — aggregates only) + migration, `tests/`.

- [ ] Failing tests (pure math, exact values): feature vector assembly from a
      fake session (recency/dwell/cart flags → deterministic dict); scorecard
      P(purchase|visitor,product) on fixtures; Thompson sampling with seeded
      RNG picks the better arm ≥ 90 % after N updates; **exploration floor**
      (every product retains ≥ ε probability of top-20); **diversity
      guardrail** (no category > 60 % of the first 12 slots).
- [ ] `features.py`: per-request visitor vector from the session +
      `analytics` session signals via its public service (lazy, fail-soft) —
      NO new per-visitor storage (session-only for non-consented, mirroring
      `personalisation._has_consent` tiers).
- [ ] `reranker.py`: blend = per-product prior (dynamics
      `purchase_probability`, read via a lazy fail-soft import of its public
      service) × per-visitor affinity × Thompson sample from `RankerArmStat`.
      Registered on `PRODUCT_LIST_REORDER` at a priority AFTER personalisation
      (compose, don't fight — it reorders the already-personalised list).
- [ ] Impression/conversion updates: subscribe to existing analytics
      PRODUCT_VIEWED + ORDER_PLACED hooks → increment `RankerArmStat`
      (cache-buffered like feature_adoption, hourly flush task).
- [ ] Verify: suite green; disable litmus (reranker unhooks → lists return to
      personalisation order); p95 rerank overhead < 20 ms on a 60-product list
      (unit-benchmarked with `time.perf_counter`, asserted loosely).
- [ ] Commit: `feat(smart_merchandising): per-visitor bandit reranker on PRODUCT_LIST_REORDER (new plugin)`

### Task 3.2: Measured by experiments — the engine's first consumer + first UI

**Files:** `smart_merchandising/experiment.py`, `views_dashboard.py`,
`templates/smart_merchandising/dashboard.html`; small addition in
`experiments`: a public `get_or_create_experiment(key, variants)` service if
one doesn't exist (owner: experiments — one function, no new models).

- [ ] Failing tests: visitors split ranker/control by the existing
      experiments assignment (cookie-stable); control passes lists through
      untouched; `results_for` output rendered (revenue/visitor, CVR, lift,
      significance); **auto-holdback**: if ranker revenue/visitor < control by
      > 10 % at p < 0.05, the subscriber self-disables via plugin config and
      notifies staff.
- [ ] Dashboard page (`section='analytics'`): experiment status, arm
      performance, guardrail state, manual kill-switch. This doubles as the
      first-ever `experiments` UI — keep the rendering generic enough that a
      follow-up can lift it into `experiments` proper (note it in the code).
- [ ] Verify: suites green (smart_merchandising + experiments regression);
      boundary guard; disable litmus.
- [ ] Commit: `feat(smart_merchandising): A/B-measured rollout with auto-holdback — experiments engine's first consumer`

### Phase 3 deploy gate
- [ ] MINOR bump + release notes ("your storefront now learns per-visitor —
      and proves its lift") → push → smoke: two fresh sessions get differently
      ordered PLPs; dashboard shows assignments accruing.

---

## Phase 4 — P1: AI support inbox (new plugin `support_inbox`)

The most demoable AI feature for founders: order-aware support with Linda
drafting replies. `requires = ['orders', 'customers']`.

### Task 4.1: Tickets — storefront intake + dashboard inbox

**Files:** create `plugins/installed/support_inbox/` — `apps.py`, `app.py`,
`models.py` + migration, `views_storefront.py`, `views.py`, `urls*.py`,
`templates/support_inbox/`, `tests/`.

**Models (owner: support_inbox):**
```python
class Ticket(models.Model):
    id UUID; customer FK(AUTH_USER_MODEL, null=True); email; order FK('orders.Order', null=True)
    subject; status ('open','pending','resolved') db_index; created_at; updated_at
class TicketMessage(models.Model):
    ticket FK related_name='messages'; author ('customer','staff','ai_draft')
    body; created_at   # ai_draft never leaves the dashboard unsent
```
- [ ] Failing tests: storefront "Get help" creates ticket bound to the
      logged-in customer's order; anonymous intake requires email; staff inbox
      list/filter/reply; reply emails the customer via the existing
      `core/emails` path; permission boundaries; disable litmus (account tile
      + intake URL gone).
- [ ] Storefront: `/support/` intake + "Get help with this order" on the
      account order page via the existing `ACCOUNT_SUMMARY_FIELDS`-style
      contribution (whatever the account-page extension hook is — verify at
      build time; worst case a StorefrontBlock on the account slot).
- [ ] Dashboard: inbox list (status pills, unreplied-first), ticket thread
      view with reply box; `section='customers'`.
- [ ] Commit: `feat(support_inbox): order-aware customer support tickets (new plugin)`

### Task 4.2: Linda first-responder (propose-only)

- [ ] Failing tests: draft generation is triggered on new inbound message and
      stores an `author='ai_draft'` TicketMessage (never auto-sends); the
      draft's order facts come from the ticket's own order (no cross-customer
      leakage — explicit test); WISMO ("where is my order") drafts include the
      real fulfillment status; agent tools respect scopes.
- [ ] On CUSTOMER inbound (hook or signal in-plugin): background task asks the
      existing agent runtime for a reply draft with a scoped toolset
      (`orders.read` for THIS order only), stores it as `ai_draft`; staff sees
      "AI draft ready — edit & send". One-click send.
- [ ] Ops-inbox pattern for auto-send: merchant can enable auto-send for
      high-confidence WISMO only (default OFF).
- [ ] Agent tools: `support.list_open_tickets`, `support.draft_reply`
      (requires_approval).
- [ ] Verify: suite green; a seeded WISMO ticket produces a draft citing the
      real tracking state; boundary guard.
- [ ] Commit: `feat(support_inbox): Linda drafts replies with real order context — propose-only, staff-approved`

### Phase 4 deploy gate
- [ ] MINOR bump + release notes → push → smoke `/support/` intake + dashboard
      inbox + one AI draft on the live store.

---

## Phase 5 — P2: Theme contract + second theme

### Task 5.1: Document + enforce the theme contract

**Files:** `docs/THEMES.md`, `scripts/check_theme_contract.py`,
`themes/library/dot_books/theme.py` (docstring only if needed).

- [ ] Enumerate the actual contract from `dot_books` + the registry's theme
      discovery: required templates (`storefront/base.html`, home, PLP, PDP,
      cart, checkout bridge), required blocks/slots each template must render
      (`{% storefront_blocks %}` calls — grep the canonical slot list from
      `plugins/contributions.py`), `theme.py` metadata surface, sections/
      customizer expectations.
- [ ] `check_theme_contract.py <theme>`: verifies required templates exist,
      compile, and render every canonical slot; wire as a CI step for
      `themes/**` changes.
- [ ] Verify: checker passes on dot_books; deliberately broken fixture fails.
- [ ] Commit: `docs(themes): theme contract + CI conformance checker`

### Task 5.2: Second theme — `general_store`

**Files:** `themes/library/general_store/` (theme.py, templates, sections).

- [ ] Not a book store: neutral product-first retail theme (square imagery,
      denser grid, category-forward home). Reuse storefront view contracts
      unchanged — templates + CSS tokens only, no view logic in the theme.
- [ ] All canonical slots rendered (checker green); every template compiles;
      PLP/PDP/cart/checkout smoke on local compose with the theme active
      (`MORPHEUS_ACTIVE_THEME=general_store`).
- [ ] Verify: full storefront test suite green under BOTH themes (run the
      storefront suite twice with the env var swapped).
- [ ] Commit: `feat(themes): general_store — second first-party theme, proving the theme contract`

### Phase 5 deploy gate
- [ ] MINOR bump + release notes → push (dotbooks.store keeps dot_books; the
      theme ships as an option) → smoke a compose boot with general_store.

---

## Deliberately NOT in this plan (backlog, in priority order)

- **POS / omnichannel** — different hardware/offline problem domain.
- **True multi-store** (N storefronts, one install) — needs an ADR on tenancy
  (StoreChannel exists but scoping catalog/orders/themes per channel is a
  cross-cutting migration; don't start it as a side quest).
- **Plugin marketplace/registry + `morpheus create-plugin` CLI** — ecosystem
  play; valuable after the contract stops moving.
- **Visual search / generative themes** — after Phase 1's ranking + Phase 5's
  contract exist to build them on.
- **Helm chart / load benchmarks / GDPR automation** — enterprise pack, own
  plan.

## Success criteria (whole plan)

1. A typo'd search returns the right product; suggest-as-you-type < 150 ms
   server time; zero-result report live in the dashboard.
2. A merchant can take PayPal, Apple Pay and Klarna without code.
3. Two fresh visitors see measurably different product orders, and the
   dashboard proves (or disproves) the lift with real significance — with
   auto-holdback armed.
4. A customer asks "where's my order?" and staff sends an accurate AI-drafted
   reply in one click.
5. `MORPHEUS_ACTIVE_THEME=general_store` boots a non-book store that passes
   the same test suite.
6. Every new surface passes the disable + delete litmus tests; boundary
   baseline does not grow; five deploys, five bumps, five release-notes
   entries (ADR 0032).
