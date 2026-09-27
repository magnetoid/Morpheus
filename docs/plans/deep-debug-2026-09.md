# Deep debug — 2026-09 (whole-codebase analyze → debug → fix)

Owner ask (2026-09-25): "analyze whole code and debug and fix". Method: gather
objective evidence first (every CI gate, the full suite, 72h of logs from all
nine production containers, live worker inspection), then prove each finding
with a failing test before fixing it. Seven area hunters ran in isolated
worktrees (money, AI layer, storefront/SEO, dashboard, jobs, security,
catalog/booking); every fix they proposed was re-proven against unfixed code
before it was integrated.

## Baseline (v0.75.15)

- CI had been billing-blocked, so no gate had run on recent merges. Locally:
  ruff ✓, check ✓, makemigrations ✓, release --check ✓, boundaries ✓, API
  stability ✓, 33 pytest smoke suites ✓, 620/620 templates compile. Drift:
  2 files unformatted, 1 bandit false positive, stale plugin-standard rows.
- Full suite: 3,454 tests, 2 failures + 1 error — all stale (error-page copy
  changed in 6de8146e without its test; a committed scratch `test_manifest.py`).

## Shipped

| Ver | Severity | Fix |
|---|---|---|
| v0.75.16 | critical | Anonymous callers could invoke the generic Worker (audience `any`, every merchant scope) over REST/SSE/GraphQL → `customers.search` etc.; a narrow Bearer token escalated through any agent. |
| v0.75.17 | critical | The Celery worker never registered `deliver_email` (every order/newsletter email since 2026-07-12 discarded), catalog search sync, query-embedding warm-up. Verified on the live workers before and after. |
| v0.75.18 | critical | Product editor: every save of a simple/bundle product switched stock tracking + shipping off; Featured/Taxable could not be unticked. Became reachable with v0.75.11; no live product was affected. |
| v0.75.19 | high | Stripe: a webhook whose first processing failed was 200-OK'd unprocessed on retry → paid order stayed unpaid, later auto-cancelled. |
| v0.75.19 | high | B2B bulk CSV reorder priced variant lines at the parent's 0.00 placeholder. |
| v0.75.19 | high | Booking: three overbooking paths (no-slot bookings, invented time labels splitting daily capacity, party cap skipping ticket tiers), stays ignoring `max_adults`, enquiries losing the guest's date. |
| v0.75.19 | high | Agent tools: `**fields` handlers received none of their arguments (catalog create/update, seo site settings reported success, changed nothing); update tools now refuse price edits (gated `products.update_price` only). |
| v0.75.19 | high | Back-in-stock subscribers were never emailed (task had no caller). |
| v0.75.19 | high | Agent read tools `orders.list_recent`, `orders.summary`, `analytics.revenue_summary` raised on every call (nonexistent `Order.state`/`created_at`) — found by invoking every registered tool. |
| v0.75.19 | medium | Marketplace Reports dashboard page raised on every load (`VendorPayout.created_at`) — found by crawling every dashboard URL. |
| v0.75.19 | medium | Inventory release on a re-cancelled order freed other orders' holds. |
| v0.75.19 | medium | GA4 `view_item` never sent (deferred djmoney KeyError); now crawler-filtered, at the shown price, queued off the request; line items at charged prices. |
| v0.75.19 | medium | Journal: dot books' sample essays served on the travel/herbal stores (live 500s), "booksellers" meta description on every store. |
| v0.75.19 | medium | SEO site audit 429'd by the store's own rate limiter; SIGKILLed on dotbooks every night. |
| v0.75.19 | medium | Self-improvement analyzer/verifier called a nonexistent `provider.complete()` — the LLM path never ran. |
| v0.75.19 | medium | Theme builder preview blank (X-Frame-Options DENY on same-origin frames). |
| v0.75.19 | medium | Reviews: re-posting re-published a merchant-hidden review. Profile email clash → 500. |
| v0.75.19 | medium | Catalog: agent metadata quoted 0.00 / wrong URL / "in stock" for sold-out; new variants priced in USD inside EUR products. |
| v0.75.19 | medium | Storefront/SEO (9 fixes): low-stock badge, /account/points/ title, title clamp cutting the brand ("…— Montene"), sitemap index listing unserved/disabled children, vendor pages missing from the sitemap, quick-search price bypassing the pricing seam, search query truncation (`&`, `+`, `#`), PDP stock notice disagreeing with inventory, trust-strip rating, web-story publisher logo. |
| v0.75.19 | low | Gate drift cleared; two stale tests repaired; dead scratch script removed. |

## Investigated — not bugs / deferred

- `upstream_drift: git not on PATH` — drift is defined against a customized
  fork; these containers ship the canonical tree, so zero by construction.
- "DB accessed during app initialization" — the plugin registry reads enabled
  state at boot by design (runtime-togglable apps); a lazy-activation refactor.
- `ai_assistant.on_product_created(product=None)` — a test firing a synthetic
  event; the only producer passes the instance.
- Nightly backups (`/app/backups` not writable) — owner deferred 2026-09-16.
- Storefront CSP violations (leaflet CSS, CF beacon, AMP) — the storefront
  policy is report-only, so nothing was blocked; the allow-list now matches.

## Recommendations (product decisions, not shipped)

- cms migrations seed ~11 dot books essays as **published** pages into every
  fresh store (montenegro needed a command to retire them). Seed as drafts, or
  not at all, for fresh installs.
- The analytics plugin excludes only AI crawlers; Semrush/Petal/Apple bots
  (~90% of product-page hits) count as views.
- Precompile Tailwind for the dashboard (drops the Play CDN and `unsafe-eval`).

## Second pass — "go fix all" (2026-09-27)

- **Lost email, sized:** since 2026-07-12 the only orders are 4 cancelled staff
  test orders — no customer missed an order email. The real loss: **29 newsletter
  sign-ups stuck at `pending`** (18 dotbooks, 11 supernatural) because their
  double opt-in email was dropped. New `manage.py newsletter_resend_confirmations`
  (`--dry-run`, `--since`; skips undeliverable addresses).
- **supernatural + montenegro have no outgoing email at all** (no SMTP host,
  user or password in env or StoreSettings) — every email, including storefront
  sign-in codes, is printed to the log. Needs an SMTP provider from the owner.
  Now visible: a log warning per undelivered message, and the dashboard setup
  step checks for a real transport (it used to pass on the default sender).
- **Backups fixed:** the workers mount a persistent `/app/backups` volume, but
  Docker created it root-owned and the worker runs as `morpheus`. The image now
  creates the directory owned by `morpheus`; the live volumes were chowned and a
  montenegro backup (101.7 MiB, 327 tables restorable) proved the path. The
  settings panel's directory and retention were never passed to the command —
  wired, with the ephemeral `/tmp` default removed.
- **Crawlers counted as visitors:** one detector, `core.utils.crawlers`; analytics
  pageviews / product views / searches skip crawlers (transactional events are
  kept whoever the client is); tracking uses the same detector.
- **Not done — needs owner approval:** fresh installs still seed dot books'
  essays as *published* (cms migration 0004). Changing a migration file is
  blocked by the `no_migration_writes` hook, which asks for a deliberate human
  bypass; only brand-new stores are affected.
