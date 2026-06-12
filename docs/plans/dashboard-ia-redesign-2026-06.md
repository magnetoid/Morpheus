# Dashboard IA redesign — Shopify-clear, Woo-familiar (2026-06)

**Problem (from the 2026-06-12 audit):** two navigation systems fight each
other (hardcoded base.html links + contributed sections), producing
duplicate entries (Insights twice, Products' children repeated, Assets and
Book taxonomies both hardcoded *and* contributed), an Affiliates block more
prominent than Orders, ~10 sections several of which hold one item, eleven
settings categories, and developer features scattered across 9+ pages.
Pages feel empty because forms have no width discipline inside the 1280px
container, not because of the container.

## Target main sidebar (8 items)

Home · Linda (Chat / Activity / Automations / Observability / Insights) ·
Orders (All / Drafts / Returns) · Products (All / Categories / Collections /
Content audit / Reviews) · Customers — then contributed sections in this
order: Catalog (Stockout, Book taxonomies) · Customers (CRM, Subscriptions) ·
Content (CMS, Media assets) · Marketing · SEO · Affiliates · Analytics ·
AI · Multivendor · More plugins — then Settings.

Rules: one source of truth per entry (hardcoded XOR contributed, never
both); no plugin gets its own section under 3 pages (SEO and Affiliates
qualify with 7 and 6); everything stays contribution-driven so the
disable test keeps holding.

## Phases

1. **Nav dedupe + reorder** (this PR): kill the duplicate top-level
   Insights (now a Linda child; observability renamed Observability);
   delete the hardcoded Affiliates / Assets / Book-taxonomies blocks and
   flip those plugins' DashboardPages from nav='hidden' to nav='main'
   (the TODO in the old Affiliates block asked for exactly this); crm
   pages re-tagged section 'crm'→'customers'; Users renamed Customers;
   `_SECTION_ORDER`/`_SECTION_LABELS` reworked ('growth'→"Affiliates",
   'crm' label dropped).
2. **Developers hub**: one `/dashboard/settings/developers/` page that
   renders `section='developer'` DashboardPage contributions as TABS
   (API tokens, Webhooks+Deliveries merged, Metafields, Workflows,
   Backups, Cloudflare, Caching, Errors & logs, Updates) instead of nav
   items. Disable still removes a plugin's tab.
3. **Settings consolidation**: 11 categories → ~8 (General, Payments,
   Shipping, Taxes, Sales channels [absorbs Channels + Marketplace],
   Notifications, AI, Apps); Caching folds into the Developers hub.
4. **Density pass**: list pages full container width; forms capped
   `max-w-3xl` with two-column field rows; standard page header
   (title + breadcrumb + primary action) on every page.

Each phase is one PR; merge = deploy (CLAUDE.md landmine), so phases land
separately behind the full gate set.
