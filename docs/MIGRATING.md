# Migrating between Morpheus versions

One section per release that breaks something an integrator depends on, newest
first. If a version isn't listed, it shipped no breaking change to a surface in
[`docs/API_STABILITY.md`](API_STABILITY.md).

---

## v0.125.0 — a theme renders lazy filter panels

`LISTING_FACETS` facets may now be `lazy` (book_product's Topic and Author are). A lazy
facet's `options` hold only the chosen values, with `count` set to `None`, and it carries
`more_url` and `more_label` (a page listing every value) and, from the storefront view,
`options_url` (the listing with `?facet_panel=<key>`, which answers
`{"html": "<the panel's options>"}`). A theme that renders `listing_facets` should:

- render a facet's options with `{% include "storefront/_listing_facet_options.html" with facet=f %}`,
  which prints a count only when there is one;
- on a lazy facet, fetch `options_url` when its panel opens and replace the options with the
  returned `html` (dot_books: `static/dot_books/listing-filters.js`), and link to `more_url`
  for shoppers without JavaScript.

A theme that does neither still works: its Topic and Author panels show only what is chosen.

---

## v0.124.0 — three more protected tools; the shop memory is Linda's own

`loyalty.adjust_points`, `reviews.delete` and `subscriptions.cancel` now carry
`requires_approval=True`, like every other tool that deletes, cancels, refunds or creates value.
A token, or Janus answering on its behalf, runs one only once the merchant ticks it for that
token (Dashboard → Settings → Developer → MCP tokens); until then Janus answers
`external_needs_grant`. The store's own Workers no longer run them either.

`memory.remember` and `memory.forget` are no longer offered to an API token, directly or through
Janus: `tools/list` leaves them out and a call answers "tool not exposed". Linda's own chats keep
them. `memory.recall` is unchanged.

**What to do.** Ask the merchant to tick the three tools if your integration uses them. None of our
stores' tokens had called any of the five.

---

## v0.123.1 — save_for_later's tables are dropped

`save_for_later_saveditem`, `save_for_later_pricesnapshot` and `save_for_later_sharedwishlist`
are dropped when they are empty; one that still holds rows is kept, as in v0.122.1. The app's
migration record and switch go too. From v0.123.1 you can go back to v0.123.0; to go further
back, restore the pre-deploy backup first.

---

## v0.123.0 — save_for_later is gone

`save_for_later` is removed. It shipped switched off and never worked: its cart button had
nothing behind it, and no code read or wrote its three tables. Wishlist is the one owner of
saved and shared lists (`Wishlist.share_token`, `/wishlist/shared/<token>/`), and back-in-stock
alerts are inventory's. An out-of-tree app that lists `save_for_later` in `requires` must drop
it. Its tables stay in this release; v0.123.1 drops them the way v0.122.1 dropped Wave 1's.

---

## v0.122.1 — the tables they left are dropped

v0.122.1 drops the tables v0.122.0 left behind (listed below). The deploy backs the database
up first (`/app/backups/pre-deploy`, when the image's `safe_migrate` runs the migrations).

- A removed app's table goes only when it is empty. One that still holds rows is kept, the
  upgrade logs it, and on Postgres it loses its foreign keys, so deleting a customer, order or
  channel a kept row names still works. On SQLite it keeps them.
- The experiments app's own seed, a draft `checkout_flow` experiment that no visitor was ever
  assigned to or shown, is deleted first: on its own it does not keep the table.
- The dead models' tables in the apps that stay go whatever they hold.

**Going back.** These migrations assume the release before them is v0.122.0. From v0.122.1 you
can go back to v0.122.0, but not to v0.121.0 or older: those find the tables gone. A deployment
that goes from v0.121.0 or older straight to v0.122.1 (the self-updater fast-forwards to the
newest release) can go back only by restoring its pre-deploy backup, then deploying the older
version. Deploy v0.122.0 first to keep the way back.

---

## v0.122.0 — ten apps are gone

`one_click`, `rich_post_purchase`, `smart_shipping`, `referrals`, `experiments`, `functions`,
`environments`, `journal`, `brand_kit` and `lumina` are removed, with their settings panels,
storefront blocks and hooks. An out-of-tree app that lists one in `requires`, or imports from
one, must drop it. GraphQL loses the `functions` and `currentEnvironment`, `environments` and
`deployments` queries and the `testRunFunction` mutation. The
`--morpheus-color-*`, `--morpheus-font-*` and `--morpheus-radius` CSS variables brand_kit put in
every page head are gone: a theme that used them sets its own.

**Themes.** The experiments app's template tag library left with it: a template that still has
`{% load experiments %}` no longer compiles, and its page answers 500. The three themes in this
repository loaded it in `storefront/cart.html` without using its `{% variant %}` tag; a theme
copied from one of them before this release (`morph_create_theme --from dot_books`, say) must
delete that load. brand_kit's `tokens` and `brand_kit_settings` template variables are gone too,
and render empty.

These models leave the code too:
- `customers.WishList` and `WishListItem`;
- `ai_assistant.PromptTemplate`, `AIExperiment`, `DemandForecast`, `AgentMemory` and
  `AIInteraction.prompt_template`;
- `marketing.Redirect` (seo owns redirects) and `observability.ErrorEvent` (`core.errors` owns
  the log);
- `morpheus_brain.DailyReport` and `ReportReference`, and `loyalty_points.Referral`.

Every one of their tables stays in this release. v0.122.1 drops them: a removed app's table only
when it is empty (one that still holds rows is kept, and the migration logs it), and the dead
models' tables in the apps that stay whatever they hold, the old `observability_errorevent` rows
included. Export anything you keep in them before you upgrade to v0.122.1.

---

## v0.113.0 — one webhook per event, in one shape

A merchant webhook endpoint used to receive each event twice: once from core, as the bare payload,
and once from the Webhooks app, as `{"event": …, "data": …}`, sometimes before the order was saved.
It now receives one POST, after commit, whose body is the bare payload (canonical JSON) with the
event name in `X-Morpheus-Event`. A receiver that read `body["event"]` or `body["data"]` reads the
header and the body itself. Webhook targets must be public hosts and redirects are not followed —
point an endpoint at its final URL.

**Themes.** The tracking app's own cookie banner is gone (the consent app is the one banner):
`{% tracking_consent_banner %}` renders nothing in v0.113.0 and is removed in the next minor
release — delete it from an out-of-tree theme's `base.html`.

---

## v0.81.0 — the dashboard is sections, tabs and cards

Nothing an out-of-tree app does stops working; this is what it looks like now
and what to adopt. The sidebar is a fixed list of sections; an app's pages are
tabs of one ([where entries land](PLUGIN_DEVELOPMENT.md#where-an-apps-dashboard-entries-land-v0810)).

**`DashboardPage.section` keys.** `growth`→`marketing`, `marketplace`→`vendors`,
`cms`→`content`, `catalog` and `b2b`→`products`, `crm`→`customers`,
`sales`→`orders` are aliased, so an app using them lands in the right section.
A page with `nav='main'` whose section is none of
`orders products customers marketing channels content analytics seo vendors ai`
(and no alias) is listed only in the Apps catalogue, and `manage.py check`
warns (`morpheus.W003`). Pages sharing `group=` become one tab with sub-tabs.

**Settings pages are cards.** A `nav='settings'` page is a tool card on the
settings category its `section` names (`general payments shipping storefront
channels marketing ai notifications team developer data`; `taxes`, `access`,
`settings` are aliased), with `hint=` as its description — it is no longer a
settings-sidebar link. `SettingsPanel.category` takes the same slugs; old ones
(`taxes`, `security`, `checkout`, `content`, `customers`) are aliased and
`/dashboard/settings/<old>/` redirects.

**New, optional: `DashboardCard`.** `contribute_dashboard_cards()` puts a
widget on a section's landing (`orders`, `products`, `customers`, `marketing`,
`analytics`). Exported from `morpheus.app` and `morpheus`.

**URL moves (`/dashboard/*` is not a stable surface).** `/dashboard/marketing/`
is the Marketing overview; the coupon list is `/dashboard/marketing/coupons/`.

**Templates extending `admin_dashboard/base.html`.** The `sidebar_sections`,
`settings_sections`, `products_nav_children`, `settings_category_nav` and
`nav_badges`-for-every-request context keys are gone; the shell reads
`dashboard_nav` (dashboard requests only). A page that lays out the whole main
panel itself can override `{% block section_tabs %}` and place
`admin_dashboard/_section_tabs.html` inside its own layout, as Linda's chat does.

---

## v0.80.0 — pages answer for what is on them

Search-engine plumbing, tightened on all three live stores after a crawl found
soft 404s in the sitemap and 404 pages that named URLs. What an integrator may
notice:

**Themes that extend `account/base.html`.** The shared sign-in frame now
extends your theme's `storefront/base.html` instead of being a standalone
"· Morpheus" page. Its children fill **`auth_form`** (was `content`) besides
`heading` and `subheading`; `head_title` is no longer rendered — the seo app
titles these routes. A template that still overrides `content` replaces the
whole card; rename the block.

**`{% block title %}` is gone from every storefront template.** No theme's
`storefront/base.html` ever defined it, so none of them rendered. A contract
theme (`head_contract = 1`) that still has one now fails
`themes/test_head_contract.py::DeadBlockTests`. Give a page your own name with
`{% block seo %}{% with seo_title=… %}{{ block.super }}{% endwith %}{% endblock %}`.

**No raw JSON-LD or hreflang in a contract theme.** The same test fails on a
`<script type="application/ld+json">`, an `hreflang` link or a hardcoded
`<html lang="en">` in a template that extends `storefront/base.html`. Contribute
nodes through `SEO_JSONLD_GRAPH` (booking_marketplace's `seo.py` is the model).

**Sitemap sources.** The storefront's own pages (`/products/`, `/vendors/`,
`/journal/`, `/staff-picks/`, `/about/`, `/contact/`, `/shipping/`,
`/returns/`) moved from seo's native `iter_sitemap_entries()` to the
storefront's `SITEMAP_URLS` contribution, and each index is listed only while
it has content. Read the merged list (`seo.services.sitemaps._merged_sitemap_entries`)
if you consumed the native one directly. Categories, collections, vendors and
authors are listed only with active items.

**Head rules.** A 404 carries title, description and `noindex, follow` only. A
`noindex` page carries no hreflang, prev/next or JSON-LD, and a canonical only
when the canonical is the page itself. hreflang is built from the canonical, and
a market alternate requires country codes and an indexable `?market=`. A listing
with `seo_item_count == 0` (or an empty paginator) is `noindex, follow`.

Grep template: `grep -rn "block head_title\|block title %\|block content\b" templates/account themes/library/*/templates/account`.

---

## v0.77.0 — the metrics rollup is retired

`observability` no longer ships `MerchantMetric`, the hourly and daily
`rollup_metrics` beat jobs, or the GraphQL fields `metricSeries` and
`supportedMetrics`. The rollup read `core.OutboxEvent`, which the hook bus
writes only when a NATS broker (`NATS_URL`) is configured — so on every
deployment without one it had produced nothing since 2026-07-12, and no
dashboard surface read the table. Migration `observability.0002` drops it. The
`read:metrics` GraphQL scope gates nothing now; a token that still lists it is
unaffected.

**If you queried `metricSeries`:** read the owning app's data instead — orders
through the `orders` tools (`analytics.summary`), traffic through `analytics`
(`analytics.traffic_summary`, `DailyMetric`).

Grep template: `grep -rn "metricSeries\|supportedMetrics\|MerchantMetric\|read:metrics"`.

---

## v0.65.0 — Janus is Linda's only engine

Linda's in-process agent loop is gone. Every chat turn runs on Janus, which calls
the store's tools through `/mcp/admin/v1/` with a signed per-turn identity
(`docs/MCP_SERVER.md`, "Linda turn tokens"). Remove anything that relied on the
surfaces below.

### Removed HTTP endpoints

| Removed | Use instead |
|---|---|
| `GET /api/agent-tools/openai.json`, `GET /api/agent-tools/anthropic.json` | `tools/list` on an MCP server under `/mcp/*/v1/`, which returns each tool's JSON schema |
| `GET/POST /api/mcp/tools/list`, `POST /api/mcp/tools/call` | The MCP servers under `/mcp/*/v1/` with a Bearer token from Dashboard → Apps → MCP tokens |
| `POST /dashboard/assistant/invoke/` | `POST /dashboard/assistant/stream/` (same body; server-sent events, the last one carries the result) |
| `/dashboard/agents/selfdev/` and its actions | None. The self-coding loop was removed. |
| `POST /dashboard/assistant/proposals/<id>/action/` (code proposals) | None. The staged-changes inbox at `/dashboard/assistant/proposals/` is unchanged. |

### Removed Python and commands

- `core.assistant.run_assistant`, the runtime's `AssistantMessage` dataclass, and
  `Assistant(provider=, tools=, max_steps=, scopes=, token_budget=)`. `Assistant()`
  now takes only `store=`. Drive a turn with `Assistant().stream(...)`.
- `core.assistant.consensus`, `codegen`, `apply`, `flywheel`, `evals`, and
  `core.schema_introspector`.
- Agent tools `code.draft_tool`, `code.list_proposals`, `code.evaluate_proposal`,
  `code.apply_proposal`. `run_python` stays.
- `manage.py run_assistant_evals`, `manage.py selfdev_approve`, and the
  `assistant-tool-gap-flywheel` beat task.
- Settings `LINDA_ENGINE` and `LINDA_MCP_TOKEN`. There is no engine switch and no
  static Linda credential.

### Kept on purpose

`CodeProposal` rows and their table are untouched; the model is marked retired and
nothing reads it. Dropping the table is a separate, deliberate change.

## v0.50.0 — index rules, and pagination that tells the truth

**Who this affects:** anyone whose app publishes a paginated listing, anyone who
set `SiteSeoSettings.noindex_query_params`, and any theme or app that assumed an
out-of-range `?page=` renders page 1.

### Out-of-range page numbers now 404

`/products/?page=999` used to answer `200` with page 1's products. It now
returns `404`, as does a page number that is not a number. This is the fix for a
live defect: Django's paginator clamps out-of-range numbers, so every integer
anyone appended became a separate indexable page claiming — via a self-referential
canonical — to be the original.

If you paginate a listing of your own, use the same shape:

```python
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404

try:
    page_obj = Paginator(qs, per_page).page(request.GET.get('page') or 1)
except (EmptyPage, PageNotAnInteger):
    raise Http404('No such page of results.') from None
```

…and **put `page_obj` in your template context**. The canonical now trusts
`?page=` only when a real paginator is present, so a listing that paginates
without exposing `page_obj` would canonicalise all of its pages onto page 1.
(The reverse case is what shipped: a listing with no paginator echoed `?page=`
into its canonical anyway.) `?page=1` is 301'd to the clean URL, and page 2
onwards gets `— Page N` appended to its title.

### `noindex_query_params` is superseded

Query-parameter policy now lives in one `IndexRule` row per parameter, edited at
**SEO → Index rules**, with four policies: consolidate, no-index, index only
listed values, and block in robots.txt. Your existing
`SiteSeoSettings.noindex_query_params` list **still applies** — it is read as an
implicit no-index rule, and any real rule for the same parameter overrides it —
but the field goes away with the column in a future release. Move your entries
across when convenient.

One behaviour change comes with it, and it is a fix: a no-indexed parameter page
is now **canonical to itself**. Previously it was `noindex` *and* canonical to
the bare category — two contradictory claims about two URLs, and the documented
risk is that the no-index is applied to the canonical target, i.e. the category.

### robots.txt is contributed, not hardcoded

`/cart/`, `/checkout/` and `/auth/` now come from the `storefront` app through
the `SEO_ROBOTS_RULES` filter (`value` is a `core.robots.RobotsDocument`; call
`disallow()` / `allow()` / `sitemap()` and return it). The rendered file is
unchanged. If your app publishes a private surface, contribute it rather than
asking for an edit to the seo app.

---

## v0.49.0 — products with variants are described as one item

**Who this affects:** nobody has to change anything. This adds markup that was
missing and fixes a case where it disappeared.

### What changed

A product sold in several versions — print and ebook, or several sizes — is now
described as a **ProductGroup** carrying its variants, each with its own price
and its own real stock, rather than a single Product node that mentioned none of
them. The code for this existed since v0.30 and had never run on a product page:
it was guarded on the database row while the page renders a GraphQL payload.

Products on sale now publish their **previous price**, so Google can show the
saving. It is emitted only when the compare-at price is genuinely higher than
what is being charged — a leftover compare-at price equal to the price is not a
sale and is not advertised as one.

### A bug worth knowing about

One unguarded read of a deferred money field raised `KeyError` (djmoney's
behaviour, which `getattr`'s default does not catch), and the graph's per-node
guard turned that into a product page with **no Product markup at all** — a 200
with the whole node missing. Money fields are read defensively now. If you build
JSON-LD of your own from a partially-loaded row, do the same.

---

## v0.48.0 — product markup states only what is true

**Who this affects:** anyone relying on the shipping, return-policy or
availability values in the storefront's Product JSON-LD, and any app reading
`plugins.feed_mapping.availability_to_schema`. Storefront HTML, GraphQL, REST
and webhooks are unaffected.

### What changed

The Product offer used to carry a complete shipping and return policy that the
SEO app assembled from configuration keys **nothing ever wrote** — they were not
in any settings schema and had no writer anywhere in the tree. Every store
published the same invented policy, and because the free-shipping threshold
defaulted to the truthy string `'0'`, every product page advertised **free
shipping on everything**, whatever the shipping app actually charged.

Those properties now come from the apps that own the data:

| Property | Comes from |
|---|---|
| `offers.shippingDetails` | `shipping` — the cheapest active `ShippingRate` per zone, with its real price, destination countries and transit estimate |
| `offers.hasMerchantReturnPolicy` | `returns_portal` — its configured return window, with the store's country from Settings → General |
| `offers.availability` | `inventory` — real stock per variant, including backorder policy |

Both subscribe to `SEO_JSONLD_GRAPH`. **If an owner has no data, the property is
omitted rather than defaulted.** A missing recommended property costs a warning
in Search Console; an invented one is a Merchant Center policy violation.

### Do I have to change anything?

**Only if you were depending on those values being present.** They now appear
when — and only when — they are configured:

* Configure shipping zones and rates to publish `shippingDetails`.
* Set the store country (Settings → General) to publish a return policy.
* Install/enable `inventory` for real availability; without it a product is
  reported purchasable, as before.

### Other changes in this release

- **Product pages carry their full markup again.** The page renders a GraphQL
  payload, and the markup builder skipped every database-only enrichment when
  handed one — so GTIN/ISBN identifiers, the image gallery, `aggregateRating`,
  individual reviews and the Book subtype were absent from every product page,
  and `sku` was published as `""`. It now reads the rendered payload for price
  and stock and the database row for the rest.
- **`aggregateRating` counts approved reviews only.** It aggregated every row
  while the `Review` nodes filtered, so the rating included reviews the page
  never showed.
- **`SeoMeta.sitemap_include` does something.** It shipped in v0.47.0 with no
  reader. The sitemap now honours it, and excludes `noindex` pages regardless.
- **`plugins.feed_mapping.availability_to_schema` consults `inventory`.** It
  previously read `stock_status` / `is_in_stock` off `catalog.Product`, which has
  neither, so it answered "in stock" for the entire catalogue — in the channel
  feeds as well as the markup.

---

## v0.47.0 — per-entity SEO has one owner, and one editor

**Who this affects:** anyone reading or writing `catalog.Product`'s SEO columns
(or `Category`/`Collection`'s `meta_title` / `meta_description`) from outside
this repo, and any app that read the `seo.ai_answer` metafield. Storefront
output, GraphQL, REST, MCP and webhooks are unaffected.

### What changed

A product's SEO lived in **two** places: thirteen native columns on `Product`,
edited through a block hardcoded in the dashboard's product form, and the
generic `SeoMeta` overlay, edited through a panel that only CMS pages used.
`SeoMeta` won at render time — and because `autofill_meta_for` creates a
`SeoMeta` row for every product on creation, seeded with the product's own
*name*, a merchant who typed a meta title into the product form watched the
storefront keep showing the plain name. The edit was stored and ignored.

As of v0.47 **`SeoMeta` is the single owner**, and one panel edits it for
products, categories, collections and CMS pages alike — contributed into each
form through `PRODUCT_FORM_CARDS` and the new `CATEGORY_FORM_CARDS`,
`COLLECTION_FORM_CARDS` and `PAGE_FORM_CARDS`.

### Do I have to change anything?

**Reading: no.** The native columns are still read as a fallback, and
`resolve_meta` resolves the same way it always did — except that a value a human
typed now beats one the platform autofilled, whichever table it is in.

**Writing: yes, eventually.** Writing `product.meta_title` still works today but
is deprecated: the panel writes `SeoMeta`, and once an entity has a merchant-
edited row the native column is no longer consulted. Write through `SeoMeta`:

```python
from django.contrib.contenttypes.models import ContentType
from plugins.installed.seo.models import SeoMeta

SeoMeta.objects.update_or_create(
    content_type=ContentType.objects.get_for_model(type(product)),
    object_id=str(product.pk),
    defaults={'title': 'A title', 'auto_filled': False},
)
```

The native columns are removed in a later release. To consolidate existing data
now:

```bash
python manage.py seo_backfill_meta --dry-run   # report
python manage.py seo_backfill_meta             # apply
```

It only fills blanks (and replaces values the platform autofilled), so it is
safe to re-run and cannot overwrite a merchant's edit.

### Other changes in this release

- **`seo.ai_answer` metafield → `SeoMeta.ai_answer`.** The metafield is still
  read as a fallback; the panel writes the column.
- **`<meta name="keywords">` is no longer emitted.** Engines have ignored it
  since 2009, and the field now holds the merchant's *internal* focus keyword,
  which the editor promises is not published.
- **Product pages declare `og:type=product`** instead of `website`. Nothing had
  ever written the field; the non-blank default outranked the page kind.
- **`Redirect` gained `match_type` (exact / prefix / regex), `source`, and 410**,
  and `from_path` is unique per match type rather than globally. A redirect
  target must now be site-relative — an absolute URL is refused rather than
  served as a `Location` header.
- **`SeoPage` moved to `core.seo_page`.** Import it from there when answering
  `SEO_RESOLVE_PAGE`; `plugins.installed.seo.pages.types` re-exports it.
- **Every `/dashboard/seo/…` view now requires `seo.read`, and writing requires
  `seo.write`.** Enforcement still defaults to log-only, so nothing is denied
  until a merchant switches rbac to `enforce`.

---

## v0.46.0 — the `<head>` is rendered by one core tag

**Who this affects:** anyone maintaining a **theme** outside this repo, and any
app that emitted `<head>` markup of its own. Merchants, the storefront, the
REST/GraphQL/MCP surfaces and webhook payloads are unaffected.

### What changed

SEO markup used to be the theme's job: `base.html` called `{% seo_meta %}`, page
templates called `{% seo_product_jsonld %}`, `{% seo_breadcrumb_jsonld %}` and
two dozen siblings, and every one of them wrote HTML directly. A theme that
skipped a call silently shipped a page with no canonical; a theme and a page
that both made one shipped duplicates (the product page really did emit two
`og:type` tags).

Now core builds a **head document** and fires `STOREFRONT_HEAD`; the seo app
fills it in. Themes call one tag:

```django
{% load morph %}
{% block seo %}{% storefront_head %}{% endblock %}
```

and declare `head_contract = 1` on their theme class.

### Do I have to change anything?

**Not immediately.** The old tags still work. On a page that has called
`{% storefront_head %}` they render nothing (so a half-migrated theme cannot
double-emit); on a page that has not, they behave exactly as before.

They are **deprecated** and will be removed in a later release. To migrate:

1. Replace the `{% seo_meta … %}` call in `base.html` with `{% storefront_head %}`.
   Pass your fallback copy as `title=` / `description=` if your home page needs it.
2. Delete every other `{% seo_*_jsonld %}`, `{% seo_*_og %}`,
   `{% seo_verification_metas %}`, `{% seo_llms_link %}`, `{% seo_hreflang %}`,
   `{% seo_pagination_links %}` and `{% seo_preconnect %}` call from your templates —
   all of that is in the document now.
3. Delete per-page `{% block seo %}` overrides that existed only to set
   `robots="noindex, …"`. Indexability is decided per page kind (cart, checkout,
   account and internal search are handled for you).
4. Remove any hardcoded shop name from titles: the brand comes from
   Settings → SEO / Settings → General and is applied at render.
5. Set `head_contract = 1` and run `manage.py test themes.test_head_contract`.

Tags that are NOT deprecated: `{% seo_title %}` (a string helper),
`{% seo_responsive_image %}`, `{% seo_meta_panel %}` (dashboard), and
`{% seo_ai_answer_block %}` (page body, not head).

### Two behaviour changes worth knowing

- **`robots.txt`, `sitemap*.xml`, `llms.txt`, `agents.md`, the feeds and
  `/.well-known/security.txt` are no longer language-prefixed.** On a
  multi-language store they used to resolve at `/fr/robots.txt` as well, which
  published a second copy of every discovery file per language. Only the
  unprefixed URLs answer now.
- **The IndexNow key file** is served at `/<key>.txt` only for a key matching
  the protocol's hex shape. The previous catch-all pattern shadowed any other
  root-level `.txt` route.

---

## v0.42.0 — "apps", not "plugins"

**Who this affects:** anyone maintaining an app (plugin) outside this
repository, or tooling that imports the registry. **Nobody else.** If your only
Morpheus code lives in `plugins/installed/` in this repo, it was migrated for
you — every one of the 108 shipped apps was updated in the same commit.

**Who this does not affect:** merchants, the storefront, the REST/GraphQL/MCP
surfaces, webhook payloads, and `MorpheusEvents.*` hook constants. No STABLE
surface from `API_STABILITY.md` changed. Your `.env` does not need editing.

### What changed

| Before | After |
|---|---|
| `plugins/installed/<name>/plugin.py` | `plugins/installed/<name>/app.py` |
| `from morpheus.plugin import Plugin, StorefrontBlock, …` | `from morpheus.app import Plugin, StorefrontBlock, …` |
| `from plugins.registry import plugin_registry` | `from plugins.registry import app_registry` |
| `PluginRegistry` | `AppRegistry` |
| `settings.MORPHEUS_DEFAULT_PLUGINS` | `settings.MORPHEUS_DEFAULT_APPS` |
| `settings.MORPHEUS_EXTRA_PLUGINS` | `settings.MORPHEUS_EXTRA_APPS` |
| `settings.MORPHEUS_PLUGINS_DIR` | `settings.MORPHEUS_APPS_DIR` |

**Deliberately unchanged** — these are not oversights:

- the directory `plugins/installed/<name>/`
- the base class `MorpheusPlugin` (still exported as `Plugin`)
- the `MORPHEUS_EXTRA_PLUGINS` **environment variable**, which is still read as
  a fallback. It lives in your deployment environment, not the repo, so
  renaming only the code would have silently dropped a live deployment's extra
  apps with no error anywhere. Set `MORPHEUS_EXTRA_APPS` when convenient; the
  old name keeps working.

### Find every reference in your codebase

```bash
grep -rnE 'morpheus\.plugin\b|\bplugin_registry\b|\bPluginRegistry\b|MORPHEUS_(DEFAULT|EXTRA)_PLUGINS|MORPHEUS_PLUGINS_DIR' \
  --include='*.py' --include='*.html' --include='*.md' .

# and the manifest filename itself
find . -name 'plugin.py' -path '*/plugins/installed/*'
```

### Apply the rename

```bash
# 1. the manifest file
for f in path/to/your/apps/*/plugin.py; do git mv "$f" "${f%plugin.py}app.py"; done

# 2. the symbols  (\b after 'plugin' protects the 'morpheus.plugins' logger name)
grep -rlE 'morpheus\.plugin\b|\bplugin_registry\b|\bPluginRegistry\b|MORPHEUS_(DEFAULT|EXTRA)_PLUGINS|MORPHEUS_PLUGINS_DIR' \
  --include='*.py' --include='*.html' . \
| xargs perl -pi -e '
    s/\bmorpheus\.plugin\b/morpheus.app/g;
    s/\bplugin_registry\b/app_registry/g;
    s/\bPluginRegistry\b/AppRegistry/g;
    s/\bMORPHEUS_DEFAULT_PLUGINS\b/MORPHEUS_DEFAULT_APPS/g;
    s/\bMORPHEUS_EXTRA_PLUGINS\b/MORPHEUS_EXTRA_APPS/g;
    s/\bMORPHEUS_PLUGINS_DIR\b/MORPHEUS_APPS_DIR/g;
  '
```

### Verify

```bash
python manage.py check          # every app must still be discovered
python manage.py morph_versions # your app must appear with its version
```

A missed manifest rename fails **silently**: the registry simply doesn't find
the app, so it vanishes from the catalogue instead of raising. Check the count
in the boot log (`Plugin system ready: N active`) against what you expect.

### New in the same release

Two optional manifest fields — see
[`docs/PLUGIN_DEVELOPMENT.md`](PLUGIN_DEVELOPMENT.md#4-metadata-reference):

- `protected = True` — no surface offers a disable (merchant toggle *and* AI
  tools both refuse). One-way: a manifest can add protection, never remove it.
- `system = True` — hide the app from the Apps catalogue.
