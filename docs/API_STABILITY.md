# API stability contract

> *"You can't build a third-party app on us if we don't tell you what won't move."*

This document is the stability commitment we make for surfaces that integrators build against. Read it before assuming a method, field, or URL is safe to depend on.

## Surfaces and their status

| Surface | Status | What that means |
|---|---|---|
| **GraphQL `Query.cartTotals`** | **STABLE** | Field set, input types, error shape: frozen. Additions only; removals require a deprecation cycle. |
| **GraphQL `Query.product*`, `Query.products`, `Query.category*`, `Query.collection*`** | **STABLE** | Catalog read surface that the storefront depends on. |
| **GraphQL `Mutation.checkoutComplete`, `cartAdd`, `cartRemove`, `cartUpdate`** | **STABLE** | Checkout state machine. The state names + transitions are frozen. |
| **REST `/api/graphql/`** | **STABLE** | Endpoint URL + auth header + content-type. |
| **REST `/api/health/`, `/api/ready/`** | **STABLE** | For load balancers and uptime monitors. |
| **MCP server at `/mcp/v1/`** | **STABLE** | JSON-RPC 2.0 shape, bearer auth, tool/resource registry. Tool *names* are stable; tool descriptions can be edited. |
| **Webhook payloads (`order.paid`, `order.cancelled`, …)** | **STABLE** | Event types, top-level keys, HMAC-SHA256 signing. |
| **`core.hooks.MorpheusEvents.*` constants** | **STABLE** | Plugin hooks the platform fires. Removing one is a breaking change. |
| **Plugin manifest fields (`name`, `version`, `requires`, `contribute_*`)** | **STABLE** | The plugin contract. |
| **`/llms.txt`, `/llms-full.txt`, `/md/products/<slug>`** | **STABLE** | AI-crawler discovery surface. Schema additions only. |
| **Internal Python imports (`plugins.installed.<x>.services.*`)** | **NOT STABLE** | Subject to refactor. Cross-plugin imports should go through `core.hooks` or `core.agents` instead. |
| **`agent_metadata` schema on Product/Category/etc.** | **NOT STABLE** | Free-form `JSONField` today. Will gain a schema once the surface is exercised by enough integrators. |
| **`/dashboard/*` URL paths** | **NOT STABLE** | Admin UI URLs can move (e.g. `/dashboard/start/` → `/dashboard/apps/store_bootstrap/start/` in v0.49). Build dashboard customisations on the plugin contribution APIs, not URL scraping. |

## Versioning policy

- Major version bumps signal breaking changes to **STABLE** surfaces.
- Minor versions add capabilities; never remove.
- Patches are backwards-compatible bug fixes only.
- Deprecation cycle: an entire minor version with both the old + new surface live, the old one returning `Deprecation` header + a `deprecated: true` field in GraphQL responses.

## Breaking-change announcement

Anything that breaks a **STABLE** surface ships with:

1. A `CHANGELOG.md` entry tagged `[BREAKING]`.
2. A migration script (`manage.py migrate_<name>` or equivalent) when DB data moves.
3. A grep-template integrators can run on their codebase to find references.
4. The previous minor version stays on a security-only branch for at least 90 days after the major bump.

## Breaking changes shipped

| Version | Surface | What broke | Migration |
|---|---|---|---|
| **v0.65.0** | Assistant HTTP + Python surface | Removed `/api/agent-tools/{openai,anthropic}.json`, `/api/mcp/tools/{list,call}`, `/dashboard/assistant/invoke/`, the self-coding dashboard and code-proposal actions, `core.assistant.run_assistant`, `Assistant(provider=…, tools=…)`, the `code.*` drafting tools, `run_assistant_evals`, `selfdev_approve`, and the `LINDA_ENGINE` / `LINDA_MCP_TOKEN` settings. Linda runs only on Janus. | [`MIGRATING.md`](MIGRATING.md#v0650--janus-is-lindas-only-engine) |
| **v0.50.0** | Storefront listings — pagination and canonicals | An out-of-range or non-numeric `?page=` now returns **404** instead of rendering page 1, and `?page=1` is **301**'d to the clean URL. The canonical trusts `?page=` only when the view exposes a real paginator as `page_obj`, so a paginated listing that does not put `page_obj` in its template context will canonicalise every page onto page 1. Query-parameter policy moved from `SiteSeoSettings.noindex_query_params` (still read as a fallback) to `IndexRule` rows, and a no-indexed parameter page is now canonical to **itself** rather than to the bare path. `/cart/`, `/checkout/` and `/auth/` in robots.txt are contributed by `storefront` via `SEO_ROBOTS_RULES` (`value` is a `core.robots.RobotsDocument`). | [`MIGRATING.md`](MIGRATING.md#v0500--index-rules-and-pagination-that-tells-the-truth) |
| **v0.48.0** | Storefront Product JSON-LD | `offers.shippingDetails` and `offers.hasMerchantReturnPolicy` are no longer synthesised by the seo app; they are contributed by `shipping` and `returns_portal` and are ABSENT when unconfigured (they were previously always present, with invented values including free shipping on everything). `offers.availability` now reflects real stock. `plugins.feed_mapping.availability_to_schema` consults `inventory`. | [`MIGRATING.md`](MIGRATING.md#v0480--product-markup-states-only-what-is-true) |\n| **v0.47.0** | App authoring — per-entity SEO storage | `catalog.Product`'s native SEO columns (`meta_title`, `meta_description`, `focus_keyword`, `canonical_url`, `og_*`, `twitter_*`, `noindex`/`nofollow`) and `Category`/`Collection.meta_*` are deprecated in favour of `SeoMeta`; they are still READ as a fallback but the dashboard no longer writes them. The `seo.ai_answer` metafield moved to `SeoMeta.ai_answer` (still read as a fallback). `SeoPage` moved to `core.seo_page`. `Redirect.from_path` is unique per `match_type` rather than globally, and a redirect target must be site-relative. | [`MIGRATING.md`](MIGRATING.md#v0470--per-entity-seo-has-one-owner-and-one-editor) |
| **v0.46.0** | Theme authoring — the `<head>` contract | The per-tag SEO helpers (`{% seo_meta %}`, `{% seo_*_jsonld %}`, `{% seo_*_og %}`, `{% seo_verification_metas %}`, `{% seo_llms_link %}`, `{% seo_hreflang %}`, `{% seo_pagination_links %}`, `{% seo_preconnect %}`) are deprecated in favour of one core tag, `{% storefront_head %}`. They still work, and go silent on a page that used the new tag. Discovery files (robots.txt, sitemaps, llms.txt, feeds) are no longer language-prefixed. | [`MIGRATING.md`](MIGRATING.md#v0460--the-head-is-rendered-by-one-core-tag) |
| **v0.42.0** | App (plugin) authoring — the manifest **filename** and the **import path**, not the manifest *fields* | `plugin.py` → `app.py`; `morpheus.plugin` → `morpheus.app`; `plugin_registry`/`PluginRegistry` → `app_registry`/`AppRegistry`; `MORPHEUS_DEFAULT_PLUGINS` / `MORPHEUS_EXTRA_PLUGINS` / `MORPHEUS_PLUGINS_DIR` → `…_APPS` / `MORPHEUS_APPS_DIR` | [`MIGRATING.md`](MIGRATING.md#v0420--apps-not-plugins) — grep template included |

Notes on v0.42.0, because the row above is narrower than it looks:

- The **manifest fields** (`name`, `version`, `requires`, `contribute_*`) are unchanged and remain STABLE. Only the file it lives in and the module you import from moved.
- **No STABLE runtime surface changed**: GraphQL, REST, MCP, webhooks and `MorpheusEvents.*` are all untouched.
- The `MORPHEUS_EXTRA_PLUGINS` **environment variable** still works. It lives in the deployment environment rather than the repo, so it gets a permanent fallback instead of a rename.
- Under 0.x, a break like this ships as a MINOR bump. The "major version signals breaking changes" rule above starts applying at 1.0.0.

**Not yet stable, and known to be so:** app and theme *update channels*. There is
no per-component update source; the platform updater is whole-platform and
git-based, and it is inert on container deployments. Do not build against it
yet — see [`UPDATING.md`](UPDATING.md).

## What's NOT covered

- Themes — they're freeform templates; we don't promise template tags or CSS class names won't change.
- Storefront URLs (`/products/<slug>/`, `/journal/<slug>/`) — themable, merchant-controlled.
- Internal plugin services. If you import `from plugins.installed.orders.services import OrderService`, you're on your own.

## Where to file API concerns

Open an issue tagged `api-stability` with a concrete usage example and the version you're integrating against. Stability is a contract we owe integrators — call us on it.
