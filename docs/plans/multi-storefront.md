# Multi-storefront — 2026-06

> **Status: PLANNED — approved, not started.** Decision recorded as ADR 0018
> (`.torsor/architecture/decisions/0018-*`). Execute in a dedicated session,
> one phase per merge (Coolify deploy-thrash). Start at **Phase 0**. This doc is
> self-contained — a fresh session can resume from it alone.

**Goal (user):** one Morpheus backend + **one product database** serving
**several storefronts** — different domains, languages, curation, branding,
SEO and analytics — while the catalog stays centralized. In the dashboard the
owner picks **what is shared vs. per-storefront**. Each storefront reports its
own performance separately.

## The honest framing: multi-storefront ≠ headless

These are two orthogonal axes and only the first is needed here:

- **Multi-storefront** (this plan) = data + routing: "this domain → this
  storefront → these products, this theme, this SEO/analytics scope." Stays
  **server-rendered**, so the ~46 plugins that contribute storefront surfaces
  via `{% storefront_blocks "slot" %}` keep working per-storefront.
- **Headless** = presentation-delivery: a separate JS app rendering over the
  API. **Deliberately deferred.** It strands every server-rendered plugin block
  until each is re-implemented in JS, and it is *not required* for multiple
  storefronts. Headless stays a later, **per-channel opt-in** over the GraphQL
  API that already exists — any one storefront can go headless without forcing
  the others to. (ADR 0018.)

## What already exists (we are ~30% there, not greenfield)

`core/models.py` already ships the multi-tenant spine:

- **`StoreChannel`** — UUID, `slug`, `name`, `domain` (unique), `currency`,
  `default_country`, `country_codes`, `is_default`, `is_active`, plus
  **`resolve_for_request(request)`**: host → channel, else `is_default`, else
  first. **This is the storefront primitive.**
- **`ProductChannelListing`** — per-channel `price_amount` / `cost_amount` /
  `is_published` / `visible_in_listings` / `available_for_purchase` against a
  single shared `catalog.Product` (generic FK, core stays decoupled). **This is
  "shared products, different per storefront"** — overrides, not duplication.
- GraphQL already exposes `current_channel_id(info)`; `APIKey` can bind to a
  channel.

What's missing is the **wiring that makes a channel actually drive a
storefront**: theme-per-channel, request-time catalog scoping, and a channel
dimension on SEO + analytics + the dashboard.

## Vocabulary

A **storefront** = a `StoreChannel` row. "Channel" (the model name) and
"storefront" (the product word) are the same thing. We keep the model name
`StoreChannel` and say "storefront" in the UI.

## What is an app vs. a row (ownership)

Three distinct things, deliberately split:

| Piece | Where it lives | Why |
|---|---|---|
| `StoreChannel` model + `resolve_for_request` | **core** (`core/models.py`, exists) | request routing + catalog/checkout scoping is foundational; can't be a disable-able plugin (disabling it would break the live spine, like `request_id`/hooks). |
| The storefront **renderer** | the existing **`storefront` plugin** (one app) | one app renders **all** channels; never cloned per storefront. |
| Per-channel **overrides** (`ProductChannelListing`, seo/analytics channel FK) | each owning plugin | contributed, disable-safe. |
| The **Storefronts management UI** (CRUD over channels + the "shared vs. per-storefront" controls) | a **new `stores` plugin** | it's a dashboard surface → must be a contribution that vanishes on disable; gives the admin UI clean disable-isolation. |

So: a storefront is **data (a row), not an app**. Adding a storefront = adding a
`StoreChannel` row in the `stores` dashboard — not installing a plugin. The
`stores` plugin **administers** channels; it does **not** own the model (core
does) and does **not** render them (the `storefront` plugin does).

## Architecture

```
request ─▶ ChannelMiddleware
             request.channel = StoreChannel.resolve_for_request(request)   (core, exists)
           │
           ├─▶ ThemeLoader picks channel.theme   (themes: today a global singleton → per-channel)
           ├─▶ storefront views filter catalog to request.channel via ProductChannelListing
           ├─▶ seo overrides resolved for request.channel
           └─▶ analytics events stamped with request.channel
```

**Single source of truth for host→storefront is `resolve_for_request`.** No
view, plugin, or middleware hand-parses the `Host` header to pick scope — they
read `request.channel`.

### Sharing model (the dashboard "shared vs. per-storefront" control)

Shared **by default**, override **only where it differs** — never a parallel
table per storefront:

| Concern | Default | Per-storefront override |
|---|---|---|
| Product (title, images, content) | shared `catalog.Product` | — (one owner) |
| Price / publish / visibility | `Product.price` | `ProductChannelListing` row (exists) |
| Cart / checkout pricing + currency | base price | channel listing price in `channel.currency` (a cart is bound to one channel) |
| Catalog scope (which products) | all published | channel collection/category filter |
| Theme + language/locale | global active theme | `channel.theme` + `channel.locale` |
| SEO (title/meta/schema overrides) | global default | `channel` FK on the seo override |
| Analytics | aggregate | `channel` dimension + dashboard filter |
| Currency / country | settings default | `channel.currency` / `default_country` (exists) |

One concept = one owner (CLAUDE.md). A storefront difference is a channel-scoped
**override row keyed by `channel` FK**, never a forked model or a second
storefront plugin.

## Single-store stays simple (progressive disclosure) — hard rule

**If there is only one storefront, the dashboard looks exactly like it does
today — zero added complexity.** All multi-storefront UI is gated on
`StoreChannel.objects.count() > 1` (equivalently: a non-default channel exists):

- The **storefront switcher / "which storefront?" filter** (analytics, product
  panels) is **hidden** with one store — there's nothing to switch between.
- The product form's **per-storefront panel** does **not** render; the product
  has one price/visibility, as today.
- Analytics shows a single aggregate, no channel column.
- The **Storefronts** page still exists (that's where you create the second
  store), but it's the *only* new surface, and it sits quietly under settings —
  it does not sprinkle channel controls across every existing screen.

The moment a second `StoreChannel` is added, the switchers/filters/panels appear.
Remove the second store → they fold away again. The single gate every surface
checks is **`StoreChannel.has_multiple()`** — a cached classmethod that **lives
in core** (`core/models.py`), *not* in the `stores` plugin. It must be core
because `seo`, `analytics`, and the product form call it: if it lived in
`stores` and `stores` were disabled, those gates would raise `ImportError`. The
`stores` plugin owns only the CRUD *UI*; the model and its helpers stay core.
No view hard-codes the multi-store affordance unconditionally.

## Phases (each independently shippable; one merge at a time — Coolify thrash)

### Phase 0 — default channel + the `request.channel is None` contract *(must land first)*
The site is single-store today; the multi-store machinery only works if there is
always exactly one sensible default. This phase adds **no UI** and is invisible.
- **Bootstrap a default channel.** A data migration ensures one `StoreChannel`
  exists with `is_default=True`, `domain` = the current production host, currency
  from settings. **Idempotent** (`get_or_create` on `is_default`); safe to run on
  the live DB. Until it runs, `resolve_for_request` returns `None`.
- **Define the `None` contract once.** `request.channel` may be `None` (no
  channels yet, or a non-storefront/admin request). **`None` ⇒ today's global
  behavior** — every consumer (theme, catalog, seo, analytics) treats `None` and
  "the default channel" identically. No consumer may crash on `None`.
- **`ALLOWED_HOSTS` is now load-bearing.** Each channel `domain` must be in
  `ALLOWED_HOSTS` or Django 400s the request before resolution. Document that
  adding a storefront = adding its domain to `ALLOWED_HOSTS` (and to the
  Coolify/Traefik + Cloudflare host config — see the proxy-chain memory). The
  `stores` create form should warn when a domain isn't yet allowed.
- **Verify:** fresh DB → migration creates exactly one default; re-run →
  no duplicate; request with unknown host → falls back to default (not a crash).

### Phase 1 — channel resolution + theme-per-storefront *(foundation)*
- **`ChannelMiddleware`** (core or storefront plugin): set `request.channel =
  StoreChannel.resolve_for_request(request)`; cheap, cached per request.
- **Theme per channel:** add `StoreChannel.theme` (slug, nullable → falls back
  to global active). `themes/registry.py` + `loaders.py` resolve the theme from
  `request.channel.theme` per request instead of the process-global singleton.
  Keep the global default for `request.channel is None` (e.g. dashboard).
  *(Landmine: the loader is process-wide today; per-request theming must key the
  template-dir lookup off the resolved theme without leaking across requests.)*
- **Storefront views scope to `request.channel`:** catalog reads filter via
  `ProductChannelListing` (publish/visibility) for the active channel; fall back
  to `Product` when no listing exists.
- **Cart/checkout pricing follows the channel.** A `Cart` is bound to the
  channel it was created in (currency can't change mid-cart). The price-breakdown
  path (the live `CART_CALCULATE_BREAKDOWN` hook) reads `ProductChannelListing`
  price for `request.channel`, falling back to `Product.price`; orders record the
  channel + its currency. *(Single-store: `request.channel` is the default, so
  this is identical to today.)*
- **New `stores` plugin** (`plugins/installed/stores/`): owns the **Storefronts**
  dashboard page — CRUD over `StoreChannel` (name, domain, currency, country,
  theme, default flag), owner-gated, via `contribute_dashboard_pages()`. Register
  in `MORPHEUS_DEFAULT_PLUGINS`. No model of its own (the model is core); it's the
  admin surface. Disable it → the management page disappears, channels keep
  resolving (the spine is core).
- **Verify:** two channels on two hosts resolve to two themes + two product
  scopes; `resolve_for_request` host-match / default / first covered;
  permission-boundary tests on the Storefronts page.

### Phase 2 — per-storefront SEO
- Add a nullable `channel` FK to the seo plugin's override model(s); resolve
  title/meta/structured-data for `request.channel` (null channel = global
  default). Sitemap + robots per channel/domain.
- **Cross-domain duplicate-content guard (important):** the same product on two
  domains is duplicate content. Emit a **per-channel canonical** (to *this*
  storefront's domain) and, when channels are language variants, **`hreflang`**
  links between the sibling channels. This is the SEO-correctness reason the user
  cares about per-storefront SEO, not just cosmetics.
- **Verify:** same product, two channels → two `<title>`/meta sets + correct
  canonical host each; null-channel default still applies where no override
  exists; sitemap at each domain lists only that channel's published products.

### Phase 3 — per-storefront analytics
- Stamp `analytics.AnalyticsEvent` (and rollups) with the resolved `channel`.
- Dashboard analytics gain a **storefront filter** (all / per-storefront).
- **Verify:** events split by channel; "all" aggregates; backfill/null-channel
  rows treated as the default storefront.

### Phase 4 — per-storefront product-sharing UI
- On the product form, a **per-storefront panel**: publish/hide, price override,
  collection membership per channel (writes `ProductChannelListing`).
- Bulk: assign a collection/category to a storefront.
- **Gated by `stores.has_multiple()`:** with one store the panel is absent and
  the form is unchanged from today.
- **Verify:** with one store the product form has no per-storefront panel;
  with two, toggling a product off for storefront B hides it on B's domain,
  stays visible on A; price override applies only on its channel.

## Deliberately deferred
- **Headless / JS frontend.** Per-channel opt-in over the existing GraphQL API,
  later. Not in scope (ADR 0018). The GraphQL surface (cart/checkout mutations
  included) is already mature enough to drive one when a storefront wants it.
- **Per-channel orders/customers tenancy.** Orders/customers are global today.
  If a storefront ever needs isolated customer accounts, that's a separate,
  larger tenancy decision — don't pre-build it.
- **Channel-scoped inventory.** Single shared stock for now; per-channel
  availability is the `available_for_purchase` flag, not separate stock pools.

## Landmines
- **Page/fragment cache must vary by channel (correctness-critical).** Any HTML
  cache — Django cache middleware, `{% cache %}` fragments, the `caching` plugin's
  edge cache, `api/cache.py` — that doesn't include the channel (or host) in its
  key will serve **storefront A's HTML to storefront B**. Every storefront cache
  key gains a channel/host component; audit existing keys in Phase 1 before
  enabling per-channel themes. This is the #1 silent bug of this whole feature.
- **Theme-per-request vs. Django's template cache.** Django instantiates template
  loaders **once** and the cached loader keys compiled templates **by name** — two
  themes with the same template name would collide and serve the wrong one. The
  per-request theme must be carried in a **request-scoped thread-local** that the
  `ThemeLoader` reads, and the active theme must be part of the template-cache key
  (or the cached loader bypassed for storefront templates). This is the single
  hardest technical risk — prototype it in isolation before wiring Phase 1.
- **FK-type retargets** on any channel migration → `RemoveField`+`AddField`,
  never `AlterField` (sqlite hides the Postgres crash; CI Postgres job is the
  gate).
- **`has_multiple()` / channel helpers live in core, not `stores`** — so
  disabling the `stores` plugin can't break the seo/analytics/product-form gates
  that call them.
- **Disable-test:** storefronts is a core capability (channels live in
  `core/models.py`); the per-channel *surfaces* (the `stores` management page,
  seo/analytics overrides) stay contributed by their plugins and vanish on
  disable — but channel *resolution* keeps working (it's core).
- **Don't fork the storefront plugin.** One storefront app renders N channels.
  A second storefront is a `StoreChannel` row, never a `storefront2` plugin.
- **Tests must set `HTTP_HOST`.** Channel resolution keys off the request host;
  `self.client.get(url, HTTP_HOST='b.example')` is how you exercise channel B.
  A test that omits it always hits the default channel.

## Verification per phase
`ruff check . && ruff format --check .`, `python manage.py check`,
`makemigrations --check --dry-run`,
`DATABASE_URL='sqlite:///:memory:' python manage.py test <touched packages>`;
rely on CI's Postgres `migrations` job for model changes; smoke two hosts
against the live deploy after each phase.
