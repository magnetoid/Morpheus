# Morpheus OS — Open-Core Completeness Plan (2026-08)

**Status:** APPROVED DIRECTION — execution pending per-phase "ship" approvals.
**Decisions (owner, 2026-08-10):** (1) **Commercial open-core** — free Apache-2.0
core + paid Enterprise edition with real license/edition gating; (2)
**completeness first** — the free core becomes rock-solid before the edition
boundary goes in; (3) **maximal build-out** — finish half-built flows AND add
serious depth, not just wiring.

**Evidence base:** 10-analyst parallel audit + synthesis (2026-08-10, ~1.17M
tokens, every load-bearing claim re-verified against the tree). Raw synthesis
preserved in §Appendix pointers. Every file:line below was verified, not guessed.

**Verdict:** the commerce spine (catalog → cart → checkout → fulfillment) is
genuinely functional for simple/variable/digital products — real Stripe/PayPal,
atomic inventory, ledger-backed tenders, real refunds. The defects cluster in
three places: a systemic **theme slot-render mismatch** silently dropping ~12
plugins' surfaces; **half-wired advanced merchandising** (subscriptions,
bundles, draft orders); and an **agent-safety asymmetry** (Linda has no
enforcement gate). None are "feature lives in a plugin" false alarms.

---

## Ground rules (apply to every phase)

- One phase = one deployable batch = one `manage.py release` bump (merge to
  `main` IS a deploy). No phase ships without explicit "ship".
- Everything lands as plugins/contributions/hooks — disable-safe, per the
  delete/disable litmus tests. New cross-plugin coupling declares `requires`
  (plugin-boundary ratchet) and never grows the core-boundary baseline (it's 0).
- Tests: `DATABASE_URL='sqlite:///:memory:' python manage.py test <targets>`;
  any migration change additionally verified on real Postgres locally (CI
  Postgres job exists but GitHub billing may block it — don't trust sqlite alone).
- Each phase's Success block is the definition of done. Weak criteria are a
  plan bug — fix the plan.

---

## Phase P0 — Agent-safety + money-correctness (must-fix-first) · MINOR

The two classes of bug that can cost a merchant real money or let AI act
ungoverned. Small diffs, highest stakes.

### P0.1 Linda enforcement gate (B5 — the platform's own "highest security value")
`core/assistant/runtime.py:687` `_dispatch_tool` calls **none** of
`approval_registry`, `enforce_policy`, `enforce_budget`, deadline checks. The
Worker does all four (`core/agents/runtime.py:39,51,181,294,363`).

- Route Linda's `_dispatch_tool` through the same enforcement stack as the
  Worker: approval gate (fail-closed for `requires_approval` tools, honoring
  `supports_staging` semantics — see the staged-gate landmine in CLAUDE.md),
  scope check via `enforce_policy`, token budget via `enforce_budget`, and a
  deadline check. Degraded/looser operator behavior is expressed as a **policy
  config object**, never a second code path (per
  `docs/plans/kernel-hardening-eval-2026-08.md` §2.1).
- Kill-switch + price/refund caps already fire (they live inside the tools);
  this adds the missing approval + scope + budget + deadline layer.

### P0.2 Tenders forfeited on refund/return
`gift_cards/plugin.py:45` and `loyalty_points/plugin.py:79` subscribe **only**
`ORDER_CANCELLED`; `orders/refunds.py:346-355` nets tenders out of the cash
refund — so on a refund/return the customer's gift-card/points tender is
silently kept.

- Subscribe both plugins to the refund events (`PAYMENT_REFUNDED` /
  `return.refunded`) with **idempotent, prorated** re-credit of the tender
  (ledger row keyed on refund id so a retried webhook can't double-credit).

### P0.3 Fail-closed stock gate actually fails closed
`inventory/services.py:92-122` catches `DatabaseError` and continues — a DB
hiccup during `reserve_for_order` silently oversells despite the
`raise_errors=True` filter contract.

- Re-raise (or convert to `InsufficientStockError`) so the checkout
  transaction rolls back.

### P0.4 USD spend cap live on prod
`core/agents/pricing.py:11` `_PRICES` lacks `deepseek-v4-pro` → the advertised
`spend_cap_daily` guardrail never trips on prod (CLAUDE.md landmine #2).

- Add `deepseek-v4-pro` pricing to `_PRICES` (same change pattern the landmine
  prescribes).

**Success:** new tests — a Linda write-tool call without scope/approval is
refused (mirrors `core/agents/tests/test_staged_gate.py` for the operator); a
full return on an order paid partly by gift card + points re-credits the
prorated tender exactly once under webhook retry; `test_guardrails` USD cap
trips under model id `deepseek-v4-pro`; a simulated `DatabaseError` in reserve
aborts checkout. All money/agent-safety suites green.

---

## Phase P1 — Storefront slot-render repair (highest visibility) · MINOR — **SHIPPED v0.37.0**

**Audit corrections found during execution** (the audit grepped only `themes/`,
which was too narrow — recorded so the numbers in this doc stay honest):
- `auth_login_extra` was **never dead** — it renders in
  `core/auth/templates/account/otp_request.html:34`. Not a plugin-only surface.
- `journal` is **not a bug**: `journal/blocks/post.html` is a complete
  alternative post renderer (takes `post`+`blocks`) while dot_books renders
  posts itself from `entry`. Emitting it would double-render, and render empty.
  Allow-listed with a reason.
- `home_above_grid` is contributed by **dynamics via a loop** over
  `SLOT_CHOICES`, which a source grep misses entirely — the parity test
  therefore reads the **runtime registry**, not `plugin.py` text. dot_books
  deliberately dropped this slot (hero leads the page), so the real defect was
  that Autopilot *defaulted* to it: every new store auto-provisioned an
  invisible block. Fixed at the default, not the theme.
- So **4** slots were genuinely dead, not 6 — but they covered **11 plugins**:
  brand_kit + motion (`global_head`), checkout_experience + post_checkout_upsell
  + discovery_quiz + rails + referrals + smart_shipping (`checkout_extra`),
  media_3d + ugc_reviews (`pdp_below_gallery`), referrals + returns_portal
  (`account_summary_extra`).

**The single biggest honesty gap:** `dot_books` renders 13 slots, but 6 slots
that ~12 plugins contribute to have **zero render sites in the tree**:
`global_head`, `checkout_extra`, `pdp_below_gallery`, `account_summary_extra`,
`home_above_grid`, `journal`.

Consequences today: `brand_kit` design tokens and `motion` CSS inject nothing
(`brand_kit/plugin.py:38`, `motion/plugin.py:41` vs `dot_books/templates/
storefront/base.html` rendering only `global_below_body` at :1112); six
checkout plugins (`checkout_experience`, `post_checkout_upsell`,
`discovery_quiz`, `rails`, `referrals`, `smart_shipping`) + `dynamics` merchant
blocks silently drop; `media_3d`/`ugc_reviews` never appear on PDP;
`referrals`/`returns_portal` account tiles invisible. `dynamics/models.py:33,40`
even offers two of the dead slots as merchant-selectable (autopilot default
`dynamics/autopilot.py:26`) — a merchant saves a block that never displays.

- Add all 6 `{% storefront_blocks %}` render points to `dot_books` (in
  `<head>` for `global_head`; checkout template; PDP below gallery; account
  summary; home above grid; journal page). Theme edits are versioned deploys
  (ADR 0033).
- **Slot-render parity test** (the enforcement layer CLAUDE.md prescribes):
  every slot any plugin contributes to, and every `dynamics.SLOT_CHOICES`
  value, must have a matching render point in the active theme or be
  explicitly allow-listed. This permanently prevents the B1 class.
- Fix `dynamics` `SLOT_CHOICES`/`_SLOTS`/`autopilot._DEFAULT_SLOTS` + the
  false comment (`eco_impact/plugin.py:108` documents the removal — clean up).
- Verify every changed template compiles via `get_template()` (memory:
  verify-templates-compile).

**Success:** parity test green and failing-on-regression; brand_kit tokens
visibly in `<head>` of the live storefront; a `checkout_extra` contribution
renders in checkout; disable each contributing plugin → its surface vanishes
(extend `test_disable_guards`).

---

## Phase P2 — Hooks & pricing wiring · MINOR

Dead seams that advertise extensibility that doesn't exist.

- **`PRODUCT_CALCULATE_PRICE` is never fired** — 2 subscribers
  (`ai_assistant/plugin.py:105`, `functions/plugin.py:57`), zero
  `filter()` callers. Fire it in catalog price-render + cart line pricing
  (mirroring `CART_CALCULATE_BREAKDOWN`'s pattern and money-order discipline);
  add a resolution test. This is the seam dynamic-pricing/personalisation
  features hang off — required for the maximal build-out phases.
- **workflows trigger-name drift:** `workflows/models.py:23,25` uses
  `customer.created`/`agent.run_failed`; the real events are
  `customer.registered` (`core/hooks.py:698`) and `agent.run.failed`
  (`core/agents/events.py:15`). Fix choices + data migration; centralize on the
  event constants so drift can't recur.
- **`PAYMENT_CAPTURED` subscribed but never fired** (`orders/plugin.py:22,112-115`;
  payments fire `ORDER_PAID` directly): fire it from the capture path so
  `confirm_order` runs, or delete the vestigial subscriber — decide once,
  with a test either way.
- Prune truly dead constants (`CART_CREATED/UPDATED`, `PAYMENT_FAILED`,
  `AI_DESCRIPTION_GENERATED`, `AI_RECOMMENDATION_REQUESTED`) or wire them;
  add `inventory.overstock_detected` to workflows `TRIGGER_CHOICES` (its
  docstring at `core/hooks.py:705` promises workflow triggering).

**Success:** a Functions/AI pricing rule changes a displayed price end-to-end;
a `customer.registered` workflow trigger fires on signup; captured payment
reaches `confirmed` (or the dead path is gone); hook catalogue is honest.

---

## Phase P3 — Reservation lifecycle hardening · MINOR

- **Stranded DB reservations:** `orders/tasks.py` is 0 bytes; a
  pending-unpaid order holds stock forever (`payment_failed` only marks the tx
  FAILED, `payments/services/stripe.py:458`). Add a beat task auto-cancelling
  pending-unpaid orders older than N minutes (merchant-configurable, orders
  settings panel) → fires `ORDER_CANCELLED` → existing `release_reservation`
  subscribers do the rest.
- **Cart Redis hold never released on web checkout:** release happens only in
  `agentic_checkout/views.py:475-477`. Add a fail-soft
  `release_cart(cart.id)` after successful `create_from_cart`.

**Success:** test — an expired pending order releases its reservation and
`_available()` recovers; the beat schedule is registered; `.delay()` paths
smoked on the compose stack (CELERY_TASK_ALWAYS_EAGER only covers tests).

---

## Phase P4 — Advanced merchandising completion (maximal) · MINOR × 3 sub-batches

Per the "maximal build-out" decision: **build, don't amputate.** One deploy per
sub-batch.

### P4a — Subscriptions actually charge
`subscriptions/views_storefront.py:54` creates active/trialing subs without
payment; `billing/stripe_adapter.py:157` `start_subscription` is dead code;
webhook reconciler (`webhooks.py:33`) can never fire; unpaid members get the
member discount (@ priority 40).

- Wire `subscribe_view` → payment collection (SetupIntent) →
  `StripeSubscriptionAdapter.start_subscription` against
  `Plan.provider_price_id`; create local sub in `state='pending'` and let
  `invoice.paid` reconcile to active (the reconciler exists — give it
  producers). `payment_failed` → dunning state. Member discount granted only
  to active/trialing paid states.

### P4b — Draft-order conversion joins the real order path
`draft_orders/services.py:44` bare-creates an Order with **no hooks** — no
stock reserve, no `ORDER_PLACED`, no payment path (contrast
`orders/services.py:601`). This also guts B2B quote→order.

- Route conversion through/mirroring `create_from_cart`: fail-closed
  `ORDER_RESERVE_STOCK` (raise_errors), `ORDER_PLACED`, and a payment
  collection path (invoice email w/ payment link via the existing gateway
  layer). B2B `accept_quote` inherits the fix for free.

### P4c — Bundles become real
`'bundle'` is a `PRODUCT_TYPE` choice (`catalog/models.py:236`) with no
component model; sold as an opaque line that skips inventory
(`orders/services.py:211`).

- `BundleItem` model (bundle FK → component product/variant, qty, optional
  price-override) in catalog + migration (real-Postgres verified); dashboard
  card on the product form via `PRODUCT_FORM_CARDS` (the ADR 0023-safe way);
  cart/order expansion: price roll-up at add-to-cart, per-component
  reserve/commit/restock across the order lifecycle; PDP shows components
  (storefront block). Digital+physical mixed bundles follow existing per-item
  fulfillment typing.

**Success (per sub-batch):** a subscription only activates on `invoice.paid`
(webhook-driven test); a converted draft reserves stock, fires order.placed,
and is payable; a bundle sale decrements each component's stock and a
component-level restock on refund works. All migrations on real Postgres.

---

## Phase P5 — Depth features the audit says a serious engine still lacks · MINOR × 2

Maximal build-out, part 2 — table-stakes gaps that are *features*, not wiring.

### P5a — Manual capture + fulfillment-triggered capture
`payments/plugin.py:188-193` offers a capture-mode config that is schema-only;
`gateway.py:45` capture is a no-op. Implement `capture_method='manual'`
end-to-end: authorize at checkout, `gateway.capture()` on fulfillment (hook
subscriber on the fulfillment event), auto-void on cancel. This is the
standard flow for ship-then-charge merchants.

### P5b — B2B machine-customer quote API
Models + services are complete (`b2b/models.py:59` Quote,
`b2b/services.py:40 create_quote/:87 accept_quote`) but no machine-facing
create path exists (`b2b/agent_tools.py:10` is read-only). Expose a scoped
MCP tool + agent tool wrapping `create_quote`/`accept_quote` (accept → draft
order via the now-fixed P4b conversion). Scope-isolation tests (token A can't
see token B's quotes). This closes the last Horizon-1 strategy item besides
Web Bot Auth.

**Success:** an authenticated agent token requests a quote, merchant approves,
agent accepts → draft order → payable order, entirely via MCP; capture-on-
fulfillment demonstrably charges an authorized-only payment.

---

## Phase P6 — Disable-debt repayment (clean-kernel completion) · PATCH × N

Repay `docs/plans/boundary-debt-2026-07.md` — one PR per item, each extending
`test_disable_guards`:

- storefront hard-imports → contributions: `book_product` / `metafields` /
  `product_videos` (13 sites in `storefront/views/catalog.py`; PDP media via a
  gallery filter), `crm`/`cms`/`consent` (`content.py:120,179,373` —
  try/except guards absence, not disable).
- admin_dashboard hard-imports → `contribute_settings_panel` /
  `PRODUCT_FORM_CARDS`: seo (`views_split/settings.py:462,670`,
  `products.py:187,255,410`), cloudflare, metafields.
- Account sub-pages (orders list, credits, downloads, addresses) → owning
  plugins as registered storefront URLs (pattern:
  `digital_products.account_downloads`; sites at
  `storefront/views/account.py:95,184,236,349,365`).
- `demo_data` decision: register in `MORPHEUS_DEFAULT_PLUGINS` or move to dev
  fixtures (currently dead code).
- Plugin-boundary baseline (122 pairs) shrinks with every item — never grows.

**Success:** disable each named plugin → its surface disappears;
`test_disable_guards` covers each; both ratchet baselines strictly smaller.

---

## Phase P7 — Test-debt + prod-migration safety net · PATCH

- **Postgres-only booking_marketplace regression test:** apply 0001, drop the
  post-squash cols/tables, run `migrate`, assert `0002_reconcile_prod_schema`
  converges + is idempotent (the v0.34.1 outage, now reproducible in CI).
- rbac: 3 permission-boundary tests + wire `has_capability`
  (`rbac/services.py:10`, currently zero callers outside rbac) into a real
  enforcement seam (view decorator / auth hook) — prerequisite for selling it
  in the Enterprise tier (P8).
- `code_quality` collector unit tests (ruff/bandit JSON parse, severity,
  dedup, fail-soft — `core/self_improvement/collectors/code_quality.py`).
- Zero-test plugins get at least metadata smoke tests; real flow tests for
  `b2b` (quote→order) and `consent` (capture→withdraw); upgrade the four
  higher-risk metadata-only suites (`returns_portal`, `checkout_experience`,
  `post_checkout_upsell`, `smart_shipping`).
- Ratchet coverage floor up from 40%; move mypy from `|| true` to enforcing
  (`ci.yml:160,53`).

**Success:** CI reproduces the v0.34.1 divergence and proves convergence; a
granted rbac capability actually gates a view; coverage floor raised.

---

## Phase P8 — Commercial open-core boundary (the business layer) · MINOR + docs + legal

Now — and only now — the edition split, on top of a proven core. The plugin
architecture already passes the delete/disable litmus for every candidate, so
the license boundary is clean.

### Edition matrix (initial; publishable as docs/EDITIONS.md)
- **Community (free, Apache-2.0):** kernel + commerce spine — catalog, orders,
  customers, payments, inventory, tax, shipping, storefront, admin_dashboard,
  checkout_experience, promotions, gift_cards, loyalty_points, cms, seo,
  reviews/ugc_reviews, wishlist/save_for_later, media, staff_mfa (security
  table-stakes stays free), plus the mandated-core (self-improvement loop,
  `core/safety`, agent guardrails — "cannot be a togglable plugin").
- **Enterprise (paid, proprietary license):** identity — `staff_sso`, `rbac`;
  AI/agent layer (ADR 0026's explicit premium candidates) — `agent_core`,
  `agent_mcp`, `agentic_checkout`, `ai_assistant`, `ai_content`, `ai_stylist`,
  `morpheus_brain`, `personalisation`; compliance — EU AI-Act evidence export;
  B2B/marketplace — `b2b`, `marketplace`, `booking_marketplace`,
  `subscriptions`, `draft_orders`, `affiliates`; ops/scale — `backups`,
  `observability`, `environments`, `fraud_rules`, `webhooks_ui`.
- **Out of scope forever:** multi-tenant (ADR 0026 single-tenant agency model;
  pre-commit rule blocks tenant_id/RLS).
- The exact split is a business call finalized at P8 kickoff — the mechanism
  below is split-agnostic.

### Mechanism (enforced, per owner decision — not honor-system)
- `edition` field on the `MorpheusPlugin` manifest (`plugins/base.py:82-101`),
  default `'community'`.
- `MORPHEUS_EDITION` setting; a filter at the `ALL_MORPHEUS_PLUGINS` seam
  (`morph/settings.py:199-201`, the existing `MORPHEUS_EXTRA_PLUGINS` splice
  point) excludes `enterprise` plugins from `INSTALLED_APPS` + `discover()`
  unless a valid license admits them. One seam, ~30 lines, no per-plugin code.
- **Signed license key:** offline-verifiable Ed25519-signed token (licensee,
  edition, expiry, optional plugin allowlist) verified at boot; public key
  ships in core. Grace behavior on expiry = warn + degrade to community on
  next boot, never a mid-flight kill. This is the only genuinely new subsystem.
- Enterprise plugin **code** moves to a private repo over time and installs via
  the sanctioned `MORPHEUS_EXTRA_PLUGINS` seam; in-tree gating is the interim.

### Legal/packaging prerequisites (ADR 0026 prep items)
1. **CLA/DCO adopted BEFORE any external contribution** — the one true
   blocker; Apache-2.0 inbound=outbound (CONTRIBUTING.md:79-84) forecloses
   relicensing external contributions into the proprietary edition. Sole-author
   freedom holds only until the first un-CLA'd PR.
2. Superseding ADR: Apache-2.0 → open-core decision (ADR 0026 predates the
   LICENSE file; reconcile the record).
3. Reconcile front-door messaging: README.md:340 "no platform fees" vs
   CONTRIBUTING.md:82-84 open-core — publish the edition matrix so the promise
   is precise ("community edition free forever" is still true).
4. NOTICE file + SPDX headers (at minimum on Enterprise-candidate plugins);
   resolve `vendor/vibe-skills` licensing; no-GPL-in-core dependency audit.
5. Trademark "Morpheus OS" (external/legal); `pyproject.toml [project]`
   metadata if/when distributing as packages.

**Success:** with `MORPHEUS_EDITION=community` and no license, an
`enterprise`-tagged plugin is absent from `INSTALLED_APPS`, its surfaces/URLs
404, and the platform boots + full test suite passes (the ultimate
disable-test); with a valid signed key, it activates; a tampered/expired key
degrades gracefully; edition matrix published; CLA live.

---

## Deferred / Horizon-2 (tracked, separate cadence — not "fully-workable" items)

- pgvector RAG phase 2 (`ai_assistant/models.py:447` JSON-vector; native-dep
  deploy risk — ship alone).
- Native Web Bot Auth RFC 9421 (Ed25519 + JWKS + Signature-Agent) for
  non-Cloudflare merchants — last Horizon-1 strategy stub, promote when P5
  lands.
- Durable agent job queue (replace `threading.Thread` fan-out,
  `core/assistant/tools/spawn.py:271`).
- Full localization Phases 2–4 (content translation editor + AI autofill
  first; currently routing-only, `localization/views.py:14-89` read-only). XL.
- Shipping label purchase (Shippo/EasyPost) + tracking sync — quote-only today
  by documented scope choice.
- `morpheus.theme` SDK maturation (slot-registry/manifest helpers) — pairs
  naturally with the P1 parity test.

## Quick-win ledger (folded into phases above)

Slot renders + parity test (P1) · cart-hold release (P3) · trigger-name drift
(P2) · refund-UI stale note (`admin_dashboard/.../order_refund.html:61-63`
falsely says gateway reversal is unwired — one-line copy fix, ride with P0) ·
`deepseek-v4-pro` pricing (P0) · DatabaseError re-raise (P0) · manual-capture
(P5a builds it rather than dropping the field).

## Sequencing & discipline

P0 → P1 → P2 → P3 → P4a → P4b → P4c → P5a → P5b → P6 (rolling PATCHes, can
interleave) → P7 → P8. Each phase: spec-level detail worked out at execution
time against live code, full suite + both ratchets + disable-gates before
commit, one deploy per phase on explicit "ship". P8 additionally gates on the
final business sign-off of the edition matrix.
