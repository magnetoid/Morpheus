# Dashboard URL unification (retire `/dashboard/apps/`) — migration plan

Status: **proposed** (not started). The nav-location breadcrumb fix
(2026-07-10) makes the UI read correctly *regardless* of the URL mess, so this
is no longer urgent — but the underlying routing is still inconsistent and
worth unifying deliberately.

## The problem

A plugin's dashboard pages are served by **two** mechanisms that produce two
different URL trees for the same feature:

1. **`/dashboard/apps/<plugin>/<slug>/` — the dynamic DashboardPage router**
   (`admin_dashboard/urls.py:plugin_page_router`). A plugin declares
   `DashboardPage(label=…, slug=…)` and gets a sidebar entry + a route for
   free. The router only understands the flat shape `/<plugin>/<slug>/` — it
   can't express a record id.
2. **`register_urls(prefix='dashboard/<plugin>/')` — the plugin's own tree**,
   used when it needs parameterised routes (detail pages, POST actions).

So marketplace's **Vendors list** lives at `/dashboard/apps/marketplace/vendors/`
while a **vendor detail** lives at `/dashboard/marketplace/vendors/<uuid>/`.
Clicking a row jumps trees. `apps` is an internal discovery-catalogue prefix
leaking into first-party section URLs (Shopify never shows "apps" for Orders/
Products/etc.).

Some plugins already paper over this with a `DashboardPage(url=…)` override
that points the sidebar at their `register_urls` path (newsletter, gift_cards),
so even the "canonical" URL of a page is inconsistent plugin-to-plugin.

## Target end state

Every plugin's dashboard pages live under **one** prefix — the plugin's own
`/dashboard/<plugin>/…` — with list and detail in the same tree. The
DashboardPage router mounts contributed pages under that prefix instead of the
shared `/dashboard/apps/` catalogue. `/dashboard/apps/` reverts to being *only*
the app-store/discovery catalogue it's named for (`apps_view`,
`apps_store_view`), not a page-serving router.

## Migration (each step shippable, redirect-backed)

1. **Teach the router to also mount at the plugin prefix.** Register the
   dynamic page router a second time so a `DashboardPage(slug='vendors')` for
   plugin `marketplace` is reachable at BOTH `/dashboard/apps/marketplace/vendors/`
   (old) and `/dashboard/marketplace/vendors/` (new). No behaviour change yet;
   both resolve. Guard against collisions with an existing `register_urls`
   route at the same path (the plugin's own routes win).
2. **Flip canonical to the new path.** `DashboardPage._canonical_url` and the
   sidebar link builder emit `/dashboard/<plugin>/<slug>/`. Update the
   breadcrumb resolver's canonical (already centralised in
   `admin_dashboard/context_processors._canonical_url`). The nav breadcrumb is
   unaffected in label terms — only the link target changes.
3. **301 the old paths.** Add a permanent redirect from
   `/dashboard/apps/<plugin>/<slug>/` → `/dashboard/<plugin>/<slug>/` for every
   contributed page (a catch-all view, like the existing legacy
   `plugin_settings_redirect` at `admin_dashboard/urls.py:163`). Keeps
   bookmarks, external links, and in-flight sessions working.
4. **Drop the `url=` overrides.** With the plugin-prefix mount live, plugins
   that set `DashboardPage(url='/dashboard/<plugin>/…')` (newsletter,
   gift_cards, …) can delete the override — the default now equals it.
5. **Retire the `apps` page-serving router.** Once step 3's redirects have
   shipped a release and analytics show the old paths cold, remove the
   page-dispatch branch from `plugin_page_router`, leaving `/dashboard/apps/`
   as the catalogue only.

## Risk / blast radius

- Every `{% url %}` / hardcoded `/dashboard/apps/…` link in templates, tests,
  and docs. Grep `dashboard/apps/` before step 2; most go through the sidebar
  builder + breadcrumb resolver (already centralised), but audit templates.
- Tests asserting `/dashboard/apps/<plugin>/<slug>/` resolution (there are a
  few) — update alongside step 1.
- External integrations / merchant bookmarks — the 301s (step 3) cover these;
  do NOT skip them.
- Do it plugin-by-plugin or all-at-once? The router change (step 1) is global
  and cheap; steps 3–4 can be per-plugin. Recommend: global router + global
  301, then drop overrides opportunistically.

## Not doing

The core sections (Products, Orders, Customers, Settings) already live at
clean `/dashboard/<section>/` paths and are unaffected — this is only about the
plugin-contributed pages currently under `/dashboard/apps/`.
