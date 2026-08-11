# Dashboard & Settings UX consistency — audit + build plan (2026-07-16)

> Source: 4-agent parallel audit (UI patterns, settings surfaces, nav/IA,
> copy/feedback) over the live codebase, anchored against the prior
> `dashboard-audit-2026-06.md`, `dashboard-ux-2026-07.md`,
> `dashboard-ia-redesign-2026-06.md`, `dashboard-url-unification-2026-07.md`
> and ADR 0004. Findings below are deduped and ranked; each phase is a
> shippable batch with its own verification. Full evidence (file:line) is
> inline — no need to re-audit before executing.

**The one-sentence diagnosis:** the design system and conventions exist and
are good — the shell defines `_empty_state`, `_pagination`, `data-confirm`,
`morph-table`, `btn-*`, a JSON error contract, settings categories — but
adoption is ~9-plugin deep in a 60-plugin dashboard, and nothing *enforces*
any of it, so every new plugin drifts. The plan is therefore: fix the broken
(P0), converge on one contract per pattern (P1), polish copy (P2), and
**turn each converged contract into a structural test** so it stays fixed
(the CLAUDE.md "promote advisory rules to enforcement" doctrine).

---

## P0 — Actually broken (small fixes, user-facing bugs) — 1 batch

> ✅ **Shipped 2026-07-16 (v0.14.8), all 8 items.** Includes the P4 #1/#2
> enforcement (`morpheus.E001`/`E002` system check in
> `admin_dashboard/checks.py`) and regression tests
> (`test_create_form_ajax.py`, `test_contribution_taxonomy.py`). The
> create-form fix also added the missing success-navigation: dashboard.js
> now follows a `redirect` key on `{ok: true}` payloads
> (`ajax_or_redirect(..., follow=True)`), so creates land on the edit page.

1. **False "Saved" on the three `data-ajax` CREATE forms.** `dashboard.js:632`
   treats any 200 non-JSON as success; `product_new`
   (`admin_dashboard/views_split/products.py:214-234`), `customer_new`
   (`customers.py:171-188`), `coupon_new` (`marketing.py:49-66`) return
   redirect/HTML — invalid input silently drops the record and toasts
   "Saved". Their edit twins already do it right. Fix: `ajax_or_redirect` +
   `ajax_form_errors` (from `_shared.py`) on the three `*_new` views.
2. **8 settings panels are invisible + their category URL 404s** — they use
   category slugs that don't exist in `settings_categories.py:29-56`:
   `checkout` (agentic_checkout:74, post_checkout_upsell:53, one_click:44,
   returns_portal:47), `content` (journal:56), `security` (fraud_rules:20),
   `customers` (post_purchase:40), `storefront` (trust_signals:49). Fix:
   remap to real slugs (checkout→payments, content→channels,
   security→developer, customers→marketing, storefront→general) **and** add
   a system check that rejects unknown categories (enforcement, see P4).
3. **bookvault API token echoed as plaintext** in the settings panel
   (`bookvault/app.py:175` lacked `format: password`). ✅ Fixed
   2026-07-16 in this batch.
4. **gift_cards nav points at a doubled URL** `/dashboard/apps/gift_cards/gift_cards/`
   while routes live at `/dashboard/gift-cards/` (`gift_cards/app.py:60-66`).
5. **booking_marketplace uses invalid `nav='marketplace'`**
   (`booking_marketplace/app.py:46`) — renders by accident. Fix: `nav='main'`
   + a validity check.
6. **webhooks_ui Delete has no confirmation at all** (`webhooks_ui/edit.html:29`),
   and styles danger inline instead of `btn-danger`.
7. **tracking panel "mirror" fields do nothing** (`tracking/app.py:191-192`
   duplicate TrackingSettings; editing them is a no-op). Fix: remove, link to
   `/dashboard/tracking/`.
8. **ai_stylist's panel never appears on the AI settings page** —
   `settings_ai()` (`settings.py:774-954`) ignores sibling `category='ai'`
   panels. Fix: render every category='ai' panel there (generalize the
   brand_voice block).

**Verify:** view tests for the 3 create paths (invalid POST → JSON errors,
no false toast); settings hub shows all 8 remapped panels; disable-guard
suite green. *Sizing: one day-batch, PATCH release.*

## P1 — One contract per pattern (the system fixes) — 4 batches

**1.1 JSON error contract.** Canonical (already what `dashboard.js:632-648`
parses): `{"ok": false, "errors": {"field_or___all__": [{"message": "…"}]}}`
+ 4xx. Today 4 shapes coexist and 3 are silently swallowed into a generic
toast: singular `{'ok':False,'error':…}` (products.py:577+5 more sites,
newsletter:29,37, pwa:152-192, analytics:171), bare `{'error':…}`
(agent_core, bookvault, media, metafields, seo), bare-text
`HttpResponseBadRequest` (analytics, wishlist, agent_core). Migrate all to
the canonical shape (a `json_error(msg, field='__all__', status=400)` helper
in `_shared.py`; plugins import their own equivalent or return the literal
shape). *This is the highest-value single fix in the audit — it repairs
error messages that are currently invisible to merchants.*

**1.2 Destructive-action contract.** `data-confirm` modal everywhere
(~24 files still call native `confirm()`: cms/pages.html:40,
agent_core/memory.html:60, seo/redirects.html:34, settings_ai.html:302,
collection_form.html:72, dynamics/index.html:103, …); every irreversible
confirm ends with a consequence + "This cannot be undone." (variant_form:26,
coupon_form:24, live_commerce, newsletter, seo confirms are bare today);
destructive buttons = `btn-danger` (4 styles today).

**1.3 Settings: one home per domain (finish ADR 0004).**
- Kill the 6 dual surfaces (panel + hand-rolled page): bookvault (two
  'Bookvault' sidebar entries!), tracking, seo, staff_mfa, cloudflare,
  dynamics — fold panel fields into the owning page or vice versa.
- `enumNames` support in `_build_panel_fields` + both templates — ~30 enum
  fields currently show raw slugs (`na/eu/fe`, `fifo/raffle`, `climatiq`).
- Shipping-domain panels adopt `category='shipping'` (smart_shipping is in
  'general', bookvault in 'apps'; the Shipping category is empty today).
- Cross-field hygiene: payments/advanced_payments fold; store-email ×3 and
  currency ×2 duplicates get defaults + "overrides X" labels;
  `get_category('caching')` null-guard.

**1.4 Nav/IA + URLs (execute the two parked plans, they're still 100% valid).**
- `dashboard-url-unification-2026-07.md` steps 1–5: mount the DashboardPage
  router at each plugin's own prefix so list and detail stop living in two
  trees (`/dashboard/apps/marketplace/vendors` vs
  `/dashboard/marketplace/vendors/<id>` today), 301 the `apps/` paths,
  delete the 14 `url=` overrides.
- IA cleanup: split the 25-page "Marketing" mega-section (ad channels →
  "Sales channels"); fold the 1-page sections (`b2b` — rendered as "B2b"! —
  `taxes`, `shipping`) into real groups; rename hardcoded "Users" →
  "Customers" (base.html:1044); de-dual-source morpheus_brain/release_notes
  (contributed AND hardcoded, base.html:1101-1121); fix dynamics'
  marketing-section-in-settings-rail; renumber `order=` collisions; delete
  dead taxonomy keys (`sales`, `crm` icons).

**Verify per batch:** contract tests (see P4) + full admin_dashboard suite +
a click-through of the changed surfaces. *Sizing: 1.1 and 1.2 are a batch
each (mechanical, wide); 1.3 and 1.4 a batch each (design decisions are
already made above). MINOR release each.*

## P2 — Copy & visual polish system — 2 batches

- **Copy style guide** (write it into CLAUDE.md or a `docs/COPY.md`, then
  sweep): noun-first toasts ("Product saved.", majority form already),
  failures = "Couldn't {verb} {entity}." (3 prefixes today), **never
  `str(e)` in merchant messages** (booking_marketplace:277-337,
  marketplace:394, cloudflare:221, markets:80, metafields:159), prose not
  `→` arrows (affiliates/marketplace/cloudflare), curly “ ” quotes
  (straight-vs-curly split ~50/50), neutral tone (drop "Sorry —"),
  sentence-case buttons/labels ("Stockout Forecast", "Sales Channels",
  "Advanced Ecommerce" → sentence case).
- **Component polish:** one save label ("Save"; "Save changes" only on
  dirty-tracked forms — today Save×17/Save settings×5/Save changes×4/Update…),
  primary-CTA = lucide `plus` + verb (kill literal "+ New X"), lucide-only
  icons (kill emoji buttons + literal `✕`), `btn-secondary` role definition,
  distinct icons for the 4×-duplicated `trending-up`/`bar-chart-3`.
- **Formatting:** money always `|money` (25 `|floatformat` currency sites
  drop the symbol), two canonical date masks (`M j, Y` / `M j, Y · H:i`) via
  a shared filter (17+ masks today).
- **Sweeps:** `_empty_state.html` include (40+ ad-hoc), `paginate_and_sort`
  + `_pagination.html` on plugin list pages, save-bar/dirty-guard beyond the
  5 core forms.

## P3 — Decisions needed (not code yet)

- **Affiliate/vendor portals**: they extend `storefront/base.html` with
  serif type, emoji buttons, bespoke `aff-table`/`vp-table`. Either adopt
  the admin design system or formally declare them a separate
  customer-facing surface with its own mini-system. (Recommendation:
  separate surface, but replace emoji with lucide and adopt the copy guide.)
- **subscriptions IA**: make "Subscription analytics" a tab of
  Subscriptions instead of a second nav entry in Analytics.

## P4 — Enforcement (ships alongside P1, one test per contract)

The audits prove conventions don't survive without gates. Add, in the same
batches as their contracts:

1. ✅ System check: `SettingsPanel.category` must be a registered category
   (kills P0#2 forever). Shipped v0.14.8 as `morpheus.E001`.
2. ✅ System check: `DashboardPage.nav` ∈ {main, settings, hidden} — shipped
   v0.14.8 as `morpheus.E002`. (Section-taxonomy warning still open; do it
   with P1.4.)
3. Structural test: no `confirm(` in dashboard templates (allowlist empty).
4. Structural test: no `messages.error(request, str(e`)-pattern; no
   singular-`'error'` JSON key in dashboard views (baseline-and-ratchet,
   like `check_core_boundary`).
5. Structural test: `data-ajax` forms' POST views must reference
   `ajax_form_errors|json_error` (grep-level heuristic; catches the P0#1
   class).
6. Secret-masking test already exists — extend it to iterate EVERY panel
   schema and flag `token|secret|key`-named string fields lacking
   `format: password` (would have caught bookvault).

## Already fixed by prior passes (don't redo)

Design-system primitives + focus ring + one accent + sentence-case table
headers (base.html); save-bar/Cmd+S on core forms; Cmd+K palette; breadcrumbs
(auto trail, 2026-07); Insights→Linda child; Developers hub; affiliates/media/
book-taxonomies nav de-hardcoding; caching-settings unification. Tonight's
sweep also hotfixed: cartTotals resolver crash (v0.14.6), bookvault token
masking, Linda provider-contract 400 (v0.14.5).

## Execution order (recommended)

P0 → P1.1 (JSON contract) → P1.2 (confirms) → P1.3 (settings) → P1.4
(IA/URLs) → P2 (copy+polish) — with P4's matching test landing inside each
batch. P3 decisions can be made any time before P2.
