# Dashboard hubs — one taxonomy for the menu, the settings and the apps (2026-10)

**Status: shipped in v0.81.0 (2026-10-08).** Owner request (2026-10-08): "there are many apps
and so many menus — organise and simplify; group widgets onto shared pages, so one
page can carry widgets from two apps; the bigger complex apps stay as they are."
The owner approved the proposal and asked for all of it ("sredi kompletno sve").

## What was measured (2026-10-08, all three live stores)

| Surface | Before |
|---|---|
| Apps active per store | 105 to 111 |
| Links in the main sidebar | 95 to 100 (5 fixed groups + 11 contributed groups, 74 to 80 pages); the same list is the phone drawer |
| "Marketing" group | 24 links, 14 of them "X Commerce" / "X Ads" for 8 channels the Sales Channels page already lists |
| Groups holding 1 to 2 links | 4 to 5 (Catalog, AI & agents, B2b, Data tools, Developer tools) |
| Settings sidebar | ~25 links (8 categories + 14 standalone pages + 3 fixed) |
| Settings panels | 62 in 8 categories that do not match their content (Audiobooks, 3D, Motion and Turnstile under General; SEO, Journal, Flipbook under Sales channels; Analytics, PWA, Fraud rules, SSO, MFA under Developer; Roles and dropshipping under "Other apps") |
| Apps catalogue | 108 cards, one alphabetical list |

Also found on the way: the sidebar "Coupons" opened a raw debug table
(`marketing/dashboard/list.html`, `stringformat:'s'` per column) while the real coupon
manager at `/dashboard/marketing/` was in no menu at all; the sales report at
`/dashboard/analytics/` was in no menu either; three nav badge queries ran on
every storefront request because `plugin_context` computed them unconditionally.

## The model

* **Sections** are the sidebar. One fixed, core-owned list in
  `admin_dashboard/navigation.py`: Home · Linda · Orders · Products · Customers ·
  Marketing · Channels · Content · Analytics · SEO · Vendors — then Settings.
  A section with nothing in it is not shown (Vendors without `marketplace`).
* **Tabs.** Every page of a section is a tab in a strip at the top of the page.
  Core pages are tabs the shell declares; app pages join with
  `DashboardPage(section=…)`. Pages that share `group=` collapse into one tab with
  sub-tabs (Affiliates' seven pages, CRM's five, each channel's catalog + ads).
* **Cards.** `DashboardCard(section=…)` is a new contribution: a small widget an
  app puts on its section's landing page (Products, Orders, Customers, Marketing,
  Analytics). A card returns `{value, caption, rows, tone}` from a data
  callable and links to its full page; the shell draws every card the same way.
  Small apps whose whole page is a summary become a card, and their page stays
  reachable from it (`nav='hidden'`), not from the menu.
* **Settings categories** are the settings sidebar. A `nav='settings'` page is a
  tool card on its category page (the Developers-hub pattern, generalised), never a
  sidebar link.
* **One taxonomy everywhere.** The Apps catalogue groups apps by the same
  sections and categories, and says what each app adds (pages, cards, settings,
  storefront blocks).
* **Disable-safe by construction.** Tabs, cards and tool cards are contributions,
  dropped on disable; the shell keeps no app link of its own (draft orders and
  reviews, hardcoded until now, contribute their tab).
* **Legacy keys keep working.** Old `section`/`category` values map through an
  alias table (`growth`→marketing, `marketplace`→vendors, `cms`→content,
  `catalog`/`b2b`→products, `access`→team, `taxes`→shipping, …). An unknown value
  is a `manage.py check` warning (`morpheus.W003`–`W005`) instead of a page hidden
  in silence — a warning, so an older out-of-tree app never stops a boot.

## Main sidebar and tabs

| Section | Landing | Tabs (owner) | Cards on the landing |
|---|---|---|---|
| Home | `/dashboard/` | — | — |
| Linda | `/dashboard/assistant/` | Chat (core) · Activity · Automations · Observability · Memory (agent_core) · Insights (core) · AI Act evidence (agent_core) · Proposals (core, superuser) | — |
| Orders | `/dashboard/orders/` | All orders (core) · Drafts (draft_orders) · Returns (core) · Bookings · Enquiries (booking_marketplace) · Subscriptions (subscriptions) · Suppliers ▸ DSers / Zendrop | — (the region renders; nothing fills it yet) |
| Products | `/dashboard/products/` | All products · Categories · Collections · Tags (core) · Reviews (reviews) · Book taxonomies (book_product) · Stays (booking_marketplace) · Price lists (b2b) | Stockout forecast (inventory) · Content audit (core) |
| Customers | `/dashboard/customers/` | All customers (core) · Segments (customers) · CRM ▸ Overview / Inbox / Support chat / Pipeline / Tasks | Loyalty points · Referrals |
| Marketing | `/dashboard/marketing/` (new overview) | Overview (core) · Coupons (marketing) · Promotions · Gift cards · Newsletter ▸ Subscribers / Campaigns / Popups · Affiliates ▸ 7 pages · Live shopping | Coupons · Promotions · Gift cards · Newsletter · Affiliates · Eco impact · Live shopping |
| Channels | channels overview | Overview · ROAS (channels) · Google ▸ Shopping / Ads · Meta ▸ · TikTok ▸ · Pinterest ▸ · Snapchat ▸ · Microsoft ▸ · Amazon Ads · Reddit Ads | — |
| Content | cms pages | Pages · Blocks · Menus · Forms (cms) · Media (media) · Stories (product_stories) | — |
| Analytics | `/dashboard/analytics/` | Overview (core sales report) · Traffic · Real-time · Funnel · Cohorts · Attribution (analytics) · Subscriptions (subscriptions) | NPS (post_purchase) · Feature adoption |
| SEO | seo overview | the eleven seo pages, unchanged | — |
| Vendors | marketplace vendors | Vendors · Applications · Vendor orders · Payouts · Payout accounts · Reports | — |

Card-only pages (reachable from their card, not the menu): Eco impact, Feature
adoption, NPS, Stockout forecast, Content audit. Hidden as duplicates: the
marketing app's raw Coupons and Campaigns tables (the coupon manager and
newsletter campaigns are the real pages); Notifications (the bell is its entry).

Departures from the first proposal: Vendor orders stays with the other
marketplace pages (a big app keeps its pages together); Channel ROAS stays with
the channels it measures; there is no Cart recovery card, because
cart_abandonment stores no counts of its own to show (a card states only what
its app can source); Tracking is a tool card on Sales channels, beside its Ads
panel; release_notes' Version & updates replaces the shell's own card while it
is on, and About Morpheus is a Developer card as well as a user-menu link.

## Settings categories

| Category | Tool cards (pages) | Panels |
|---|---|---|
| General | Markets · Translations & languages | Store details · Permalinks (core) · GDPR / Privacy · Audiobooks · Digital downloads |
| Payments & checkout | — | Payment gateways · Advanced payments · ACP · One-click · Post-checkout upsell · Returns portal · Checkout & cart · Checkout experience · Fraud rules · Subscription billing · Marketplace (vendor commission) |
| Shipping & tax | Shipping zones · Tax regions · Bookvault | Smart shipping · Bookvault · DSers · Zendrop |
| Storefront | Dynamics · Autopilot proposals | Images · Brand kit · Motion · Immersive PDP · 3D/AR · Trust signals · PWA · Turnstile · Flipbook · 3D Bookstore · Journal · Personalised rails · Discovery quiz · Lumina · Advanced ecommerce |
| Sales channels | Tracking (GA4 / GTM) | Google Shopping · Meta · TikTok · Pinterest · Snapchat · Microsoft · Amazon Ads · Reddit Ads · Google Ads conversions · SEO · Analytics |
| Marketing | — | Affiliates · CRM · Cart recovery · Gift cards · Loyalty points · Newsletter · Post-purchase · Referrals · Eco impact |
| AI | Janus · Bootstrap a store · Morpheus Brain | AI providers · Agent guardrails · Brand voice · AI stylist |
| Notifications | Email templates (core) | Email sender + SMTP (core) |
| Team & security | Roles & users · Two-factor auth · Audit log | Roles & permissions · Staff MFA · Staff SSO |
| Developer | API tokens · Webhooks · Deliveries · Workflows · Metafields · Cloudflare · Feedback · About Morpheus · Version & updates · Errors · Caching (core) | — |
| Data | CSV import / export · Migrate from Shopify | Backups |
| Other apps | shown only when an out-of-tree app leaves its panel uncategorised | |

## Work, in order (each step ships with its test)

1. **Contract** — `DashboardPage.group`, `DashboardCard` (+ `contribute_dashboard_cards`,
   registry collect/drop, SDK export), `admin_dashboard/navigation.py` (sections,
   core tabs, aliases, `locate(path)`), the `dashboard_nav` context processor
   (dashboard requests only — the badge queries leave the storefront), checks
   E003–E005.
2. **Shell** — sidebar from sections; settings sidebar = categories + Apps; hub tab
   strip with sub-tabs; breadcrumbs only below a tab root; active state and
   settings mode from `data-nav-*` on `#main-content` (survives htmx swaps); palette
   labels from the taxonomy; Marketing overview at `/dashboard/marketing/`, coupons
   at `/dashboard/marketing/coupons/`.
3. **Apps** — re-section every `DashboardPage`; draft_orders + reviews contribute
   their tabs; cards in the apps above; card-only pages hidden.
4. **Settings** — new categories, every panel and settings page re-filed; the
   category page renders tool cards for any category; overview counts tools too.
5. **Apps catalogue** — grouped by area with an "adds" line and a filter box.
6. **Guards** — sections render for a full install; every tab answers; a disabled
   app's tab, card and tool card vanish; a card that raises shows its error state;
   unknown section/category/card section fail the check; base.html carries no app
   link; categories contract.
7. **Docs + release** — ARCHITECTURE, PLUGIN_DEVELOPMENT, MIGRATING/API_STABILITY
   (section aliases), CLAUDE.md convention, release notes (MINOR), deploy, verify
   the sidebar and tabs on all three stores.

## Found and fixed on the way

* Three shell links had led nowhere for months: the products page's "Improve
  with AI" (`/dashboard/apps/agent_core/console/`, a page removed long ago — it
  now opens Linda with the request filled in), the home page's "Agents" tile
  (`/dashboard/apps/agent_core/agents/`) and the low-stock panel's "View all"
  (`/dashboard/apps/advanced_ecommerce/low-stock/`, a page that never existed —
  it now opens the stockout forecast). All three answered 404.
* The shell linked apps that can be switched off without a guard: Import and
  Bootstrap store on Products, Export on Customers, the notifications bell, the
  CMS menus link on Settings › General. Each now leaves with its app (importers
  and store_bootstrap are off on dotbooks, so two of those buttons were dead
  there).
* Twelve icons were missing from the Remix map and drew a blank circle on real
  features (Stays, Redirects, Attribution, Feedback, NPS among them); a test now
  holds every navigation icon to a glyph.
* Three nav-badge queries ran on every storefront request; the badges are
  computed for dashboard requests only, and each only while its app is on.
