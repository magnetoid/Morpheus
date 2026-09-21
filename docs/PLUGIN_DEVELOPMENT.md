# Plugin Development Guide — the App SDK

> Full developer reference for building Morpheus plugins (apps).
> For named, repeatable procedures see [`SKILLS.md`](../SKILLS.md).
> For platform-wide laws see [`RULES.md`](../RULES.md).
> For the **Theme SDK** (the other half of the contract — themes expose the
> slots apps fill) see [`THEME_DEVELOPMENT.md`](THEME_DEVELOPMENT.md).
> For the house rule this codifies see [`CLAUDE.md` § Plugin contract](../CLAUDE.md).
> For the live modular-OS refactor + known gaps see
> [`plans/modular-os-2026-06.md`](plans/modular-os-2026-06.md).

Morpheus is a **plugin-native engine**. The core does almost nothing on its
own — it discovers plugins, builds the URL map and GraphQL schema from them,
runs hooks across them, and otherwise gets out of the way.

This is the WordPress contract, applied strictly: an **app owns all of its own
code** and lives entirely under `plugins/installed/<name>/`. The **theme**
exposes placeholders (slots); the **app fills them**. And the rule that makes
the whole thing modular — **disabling an app removes every surface it added**,
backend and storefront — falls out of the registry-driven design described in
[§5.1](#51-modularity-contract-sdk-base). Together with the
[Theme SDK](THEME_DEVELOPMENT.md), this is the base SDK everything else builds on.

This guide is your end-to-end map for shipping production-quality plugins.

---

## Table of contents

1. [Quick start (60 seconds)](#1-quick-start-60-seconds)
2. [Anatomy of a plugin](#2-anatomy-of-a-plugin)
3. [The lifecycle](#3-the-lifecycle)
4. [Metadata reference](#4-metadata-reference)
5. [Extension points](#5-extension-points)
6. [Models, migrations, indexes](#6-models-migrations-indexes)
7. [GraphQL — queries, mutations, permissions](#7-graphql--queries-mutations-permissions)
8. [URLs and views](#8-urls-and-views)
9. [Hooks and events](#9-hooks-and-events)
10. [Background tasks (Celery)](#10-background-tasks-celery)
11. [Configuration schema](#11-configuration-schema)
12. [Multi-tenancy / channel scoping](#12-multi-tenancy--channel-scoping)
13. [Testing](#13-testing)
14. [Distribution as a community plugin](#14-distribution-as-a-community-plugin)
15. [Cookbook](#15-cookbook)

---

## 1. Quick start (60 seconds)

```bash
python manage.py morph_create_plugin discount_engine \
    --label "Discount Engine" \
    --description "Per-customer discount rules." \
    --with-models --with-graphql --with-tasks
```

This generates:

```
plugins/installed/discount_engine/
├── __init__.py
├── apps.py
├── app.py            ← MorpheusPlugin subclass
├── models.py            ← starter model
├── tasks.py             ← starter Celery task
├── graphql/
│   └── queries.py       ← Strawberry mixin
├── migrations/
│   └── __init__.py
└── tests/
    └── test_smoke.py
```

Then:

```bash
# 1. Add 'plugins.installed.discount_engine' to MORPHEUS_DEFAULT_APPS in morph/settings.py
# 2. Generate the migration:
python manage.py makemigrations discount_engine
python manage.py migrate

# 3. Verify:
python manage.py check                # plugin appears in the activation log
DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.discount_engine
```

That's it — the plugin is live.

---

## 2. Anatomy of a plugin

```
plugins/installed/<name>/
├── __init__.py             # default_app_config -> apps.<NameConfig>
├── apps.py                 # Django AppConfig (label = <name>)
├── app.py               # ★ MorpheusPlugin subclass: the manifest
├── models.py               # optional: Django models
├── migrations/
│   ├── __init__.py
│   └── 0001_initial.py
├── views.py                # optional: HTTP endpoints
├── urls.py                 # optional: URL config
├── tasks.py                # optional: Celery tasks
├── services.py             # ★ all business logic lives here
├── graphql/
│   ├── __init__.py
│   ├── queries.py          # <Plugin>QueryExtension
│   └── mutations.py        # <Plugin>MutationExtension
├── tests/
│   └── test_*.py
└── management/             # optional: Django management commands
    └── commands/
```

The **only required file** is `app.py`. Everything else is opt-in.

---

## 3. The lifecycle

```
                ┌──────────────────────────────────────────────┐
                │            settings.py boot                  │
                │ MORPHEUS_DEFAULT_APPS + EXTRA_APPS        │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │ app_registry.discover(paths)              │
                │   imports each <plugin>.plugin module        │
                │   discovers MorpheusPlugin subclass          │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │ app_registry.activate_all()  (AppReady)   │
                │   1. validate dependency graph               │
                │   2. topological sort by `requires`          │
                │   3. for each plugin in order: call ready()  │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │ Each ready() registers hooks, GraphQL,       │
                │ URLs, admin, tasks, beat schedule entries    │
                └──────────────────────────────────────────────┘
```

If `ready()` raises, **only that plugin** is deactivated — siblings keep loading.
The exception is logged with a full traceback (see `plugins/registry.py:_activate`).

---

## 4. Metadata reference

| Field | Type | Required | Purpose |
|---|---|---|---|
| `name` | `str` | ✅ | Snake_case identifier. **Must equal the directory name.** |
| `label` | `str` | ✅ | Human-readable name shown in the dashboard. |
| `version` | `str` | ✅ | PEP 440-style (e.g. `0.1.0`, `1.2.3a4`). |
| `description` | `str` | recommended | One-line what-it-does. |
| `author` | `str` | optional | Default `"Morph Team"`. |
| `url` | `str` | optional | Plugin homepage / docs. |
| `requires` | `list[str]` | optional | Plugin names this depends on (topological order). |
| `conflicts` | `list[str]` | optional | Plugins this cannot coexist with. |
| `enabled_by_default` | `bool` | optional (default `True`) | `False` ships the plugin **installed-but-OFF** — the merchant opts in from Dashboard → Apps. Only affects the first run (when no `PluginConfig` row exists); after that the DB flag wins. Use it for anything that's inert without operator setup — an external integration that needs credentials/an IdP (`staff_sso`), or a protocol surface a merchant opts into (`agentic_checkout`) — as well as merchant-specific features (`booking_marketplace`). |
| `has_models` | `bool` | ✅ if you have models | If True, the plugin needs to be in `INSTALLED_APPS`. |
| `protected` | `bool` | optional (default `False`) | `True` means **no surface offers a disable** — the merchant's toggle refuses it and so do Linda's disable tools, because turning it off would soft-brick the platform. See the note below: this flag can only *add* protection. |
| `system` | `bool` | optional (default `False`) | `True` hides the app from the Apps catalogue entirely. For an app the merchant meets under a different name and never installed on purpose — `agent_core` is surfaced as Linda. Use sparingly: an app the merchant *can't see* is an app they can't reason about. |

The base class **validates** all metadata at class-definition time — typos
fail fast at import, not at runtime.

### `protected` is one-way, on purpose

There is exactly one gate — `core.safety.is_plugin_protected(name)` — and every
surface that offers a disable reads it. It returns the union of two things:

1. the static floor in `core/safety.py:PROTECTED_PLUGINS`, and
2. any app whose manifest declares `protected = True`.

A manifest can therefore **add** protection but never **remove** it. That
asymmetry is deliberate: an `app.py` is a file the AI is allowed to edit, while
`core/safety.py` sits in `FORBIDDEN_PATHS` and is not. If the flag were
authoritative in both directions, the safety boundary would be editable by the
thing it constrains.

This gate exists because the two lists it replaced had already drifted apart.
`PROTECTED_PLUGINS` was defined twice — once in `core/safety.py` gating the AI's
disable tools, once as a frozenset inside `admin_dashboard` gating the
merchant's toggle — and they disagreed on four apps. The dashboard refused to
disable `catalog`, `orders`, `payments` and `morpheus_brain`; the AI path
allowed all four. **The automated path was looser than the human one.** When you
add a classification about apps, put it on the app or in core — never a second
list inside a shell. Guarded by
`admin_dashboard/tests/test_disable_guards.py::ProtectedAppGuardTests`.

---

## 5. Extension points

All extension calls go inside `ready()`. They take effect once per process.

| Helper | What it does |
|---|---|
| `register_hook(event, handler, priority=50)` | Subscribe to a `MorpheusEvents.*` constant or any string. Lower priority runs first. |
| `register_graphql_extension(module)` | Module path of a class named `<X>QueryExtension` or `<X>MutationExtension`. |
| `register_urls(module, prefix='', namespace=name)` | Mount a URLconf module under a prefix. |
| `register_admin(Model, AdminCls)` | Register a Django admin entry. Idempotent. |
| `register_celery_tasks(module)` | Surface a tasks module to Celery autodiscovery. |
| `register_celery_beat(name, entry)` | Add a scheduled task entry (won't overwrite an existing one). |
| `register_context_processor(func)` | Add a template context processor. |

Calling any of these *outside* `ready()` raises a clear runtime error.

### 5.1 Modularity contract (SDK base)

This is the core of the App SDK. An app **lives entirely under
`plugins/installed/<name>/`** and surfaces in the rest of the product
**only by contributing** through the declarative hooks below. It never reaches
into core templates, the dashboard chrome, or a theme. Because every surface
is registry-driven, **turning the app off removes all of them at once** — the
WordPress "deactivate plugin → its widgets/menu items/shortcodes disappear"
contract.

The contribution surfaces an app may use:

| Surface | Method | Lands in | Auto-removed on disable? |
|---|---|---|---|
| **Storefront block** | `contribute_storefront_blocks()` | a theme slot via `{% storefront_blocks "slot" %}` | ✅ |
| **Dashboard page** | `contribute_dashboard_pages()` | merchant sidebar (main or settings nav) | ✅ |
| **Settings panel** | `contribute_settings_panel()` | `/dashboard/settings/<category>/` form | ✅ |
| **Email template** | `contribute_email_templates()` | central list at Settings → Email templates | ✅ |
| **Agent command** | `contribute_agent_tools()` | Linda's tool catalogue (the agent runtime + MCP) | ✅ |
| **Agent skill** | `contribute_skills()` | a named tool bundle Linda opts into | ✅ |
| **Hook subscriber** | `register_hook(event, handler)` in `ready()` | the `core.hooks` event bus | ✅ (handler isn't re-registered) |

Beyond `ready()`-time imperative registration, plugins **declaratively
contribute** features. The registry calls the `contribute_*` methods after
`ready()` and aggregates the results into platform-wide indexes
(`plugins/registry.py:_collect_contributions`) — when a merchant **enables**
the plugin, every contribution lights up at once; when they disable it,
`_drop_contributions` strips them back out.

```python
from plugins.contributions import StorefrontBlock, DashboardPage, SettingsPanel

class AdvancedShopPlugin(MorpheusPlugin):
    name = 'advanced_shop'
    label = 'Advanced Shop'
    version = '0.1.0'

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='home_below_grid',
                template='advanced_shop/blocks/recently_viewed.html',
                priority=10,
            ),
            StorefrontBlock(
                slot='pdp_below_form',
                template='advanced_shop/blocks/related_products.html',
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        # Routed at /dashboard/apps/advanced_shop/<slug>/.
        return [
            DashboardPage(
                label='Bulk price edit',
                slug='bulk-price',
                view='plugins.installed.advanced_shop.views.bulk_price_view',
                icon='edit-3',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel | None:
        # Rendered as a form under /dashboard/settings/<category>/.
        return SettingsPanel(
            label='Advanced Shop',
            schema=self.get_config_schema(),
            category='apps',           # which settings category to file under
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'show_recently_viewed': {'type': 'boolean', 'default': True},
                'low_stock_threshold':   {'type': 'integer', 'default': 5},
            },
        }

    def ready(self) -> None:
        # The 4th surface: subscribe to the cross-plugin event bus. The
        # handler is wired only while the app is active, so disabling the
        # app stops it firing — no dangling subscriber.
        from core.hooks import MorpheusEvents
        self.register_hook(MorpheusEvents.ORDER_PLACED, self.on_order, priority=80)

    def on_order(self, order, **kwargs):
        ...   # always accept **kwargs; wrap the body so a bad row can't break the chain
```

The `nav` and `section` fields on `DashboardPage`, and `category` on
`SettingsPanel`, decide *where* in the chrome the entry appears — see the
dataclass docstrings in [`plugins/contributions.py`](../plugins/contributions.py)
for the full enum of sidebar sections and settings categories.

**Storefront slot names the reference theme (`dot_books`) renders today:**

| Slot | Page · position |
|---|---|
| `home_above_grid`, `home_below_grid` | Home — top / bottom of content |
| `pdp_below_price`, `pdp_below_form`, `pdp_above_long_description` | Product detail |
| `cart_summary_extra` | Cart — order-summary panel, below the total |
| `global_below_body` | Every page — end of `<body>` |

This is the **full implemented set**; the canonical catalog (with positions
and per-slot context) lives in the Theme SDK,
[THEME_DEVELOPMENT.md § 6 Placeholders / slots](THEME_DEVELOPMENT.md#6-placeholders--slots--the-themes-core-job).
Custom themes may expose additional slots — slot names are loose strings, so a
block targeting a slot the active theme doesn't render simply shows nothing.
(There is **no** `account_nav` / `account_page` slot yet — see "planned" in the
Theme SDK; account surfaces can't be contributed the clean way until the
[modular-OS plan](plans/modular-os-2026-06.md) ships them.)

### 5.2 Email templates (the central registry)

Morpheus has **one** place for transactional email — Settings → Email
templates — the WooCommerce *Settings → Emails* analog. Core ships the
order/refund/welcome lifecycle; **plugins add their own emails to the same
list** so a merchant edits every message the store can send in one screen,
never plugin-by-plugin. Contribute an `EmailTemplateDef` per email:

```python
from morpheus import EmailTemplateDef

class AffiliatesPlugin(Plugin):
    name = 'affiliates'

    def contribute_email_templates(self) -> list:
        return [
            EmailTemplateDef(
                key='affiliate_approved',          # globally-unique, namespace it
                label='Affiliate approved',
                default_subject='You’re approved — welcome aboard',
                group='Affiliates',                # display group in the central list
                description='Sent when you approve an affiliate application.',
            ),
        ]
```

Three pieces make one email:

1. **The def** (above) — registers the email in the central list, grouped
   under `group`, editable like any core template.
2. **The default bodies** — ship `templates/emails/<key>.txt` and
   (optionally) `templates/emails/<key>.html` inside your plugin. The `.html`
   extends the shared `emails/_layout.html`. These are what the editor shows
   and what "Reset to default" restores to.
3. **The send** — call `core.emails.send_templated_email(key, to=…,
   subject=…, ctx=…)`. It renders your bodies through Django's template
   engine (so `{{ order.total }}`-style placeholders work) **but a merchant's
   dashboard override wins** — same pipeline as the core lifecycle emails.
   Failures are logged, never raised, so a flaky SMTP host can't break the
   action that triggered the email.

```python
from core.emails import send_templated_email

send_templated_email(
    'affiliate_approved',
    to=affiliate.user.email,
    subject='You’re approved — welcome aboard',   # fallback if no override
    ctx={'affiliate': affiliate, 'dashboard_url': url},
)
```

**Disable contract:** the def is contributed only while the plugin is
enabled, so disabling the plugin removes its emails from the central list
(its `templates/emails/` defaults go with the plugin directory). Don't send
plugin email with a hand-rolled `EmailMultiAlternatives` — that bypasses the
central editor and the override pipeline.

### 5.3 Giving Linda commands (`contribute_agent_tools`)

**This is how a plugin teaches Linda — the built-in assistant — to operate its
domain.** When a plugin is enabled it contributes `Tool`s; the registry adds
them to Linda's catalogue (and the MCP surface); when the plugin is disabled
the registry drops them. So Linda's power is **plugin-driven and disable-safe** —
install a plugin and she gains its commands, remove it and they vanish. A tool
is a plain function + metadata (name, description, JSON-Schema args, **scopes**);
the runtime enforces scopes before every call, so a command is only as
privileged as the scopes it declares.

```python
from morpheus import Plugin
from core.agents import tool
from core.agents.tools import ToolResult

@tool(
    name='loyalty.adjust_points',                 # namespaced: <domain>.<verb>
    description='Add or remove loyalty points for a customer. Use a negative '
                'amount to deduct. Confirm with the user before deducting.',
    scopes=['crm.write'],                          # enforced by the runtime
    schema={
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'points': {'type': 'integer'},
            'reason': {'type': 'string'},
        },
        'required': ['email', 'points'],
    },
)
def adjust_points(*, email: str, points: int, reason: str = '') -> ToolResult:
    ...  # do the work; return a dict or ToolResult
    return ToolResult(output={'ok': True, 'new_balance': 1234})

class LoyaltyPlugin(Plugin):
    name = 'loyalty_points'
    def contribute_agent_tools(self) -> list:
        return [adjust_points]
```

Conventions:
- **Name** `<domain>.<verb>` (`orders.refund`, `seo.set_meta`). The domain
  prefix is what `platform.capabilities` groups by.
- **Description** is the prompt the model reads to decide when to call it —
  write it for the model, and say when to *confirm with the user* for writes.
- **Scopes** gate it (see [§5.1](#51-modularity-contract-sdk-base) /
  `agent_mcp/scopes.py`). Read tools can use `scopes=[]` (public).
- For a related set of tools + a prompt prelude, bundle them with
  `contribute_skills()` so Linda opts into them as a unit.

**Linda also learns plugins she has *no* tools for.** She ships with
introspection tools — `plugins.describe(name)` (manifest + models + commands +
code path), `platform.capabilities` (her whole grouped toolset), the `db.*`
schema/row tools, and the `fs.*` file/doc readers. So even a plugin that
contributes nothing is operable: Linda reads its models with `db.*` and its
code/docs with `fs.*`. **But prefer `contribute_agent_tools`** — a declared,
scoped command is safer and more reliable than Linda reverse-engineering your
plugin from its schema. Expose the actions you want her to take; let
introspection be the fallback.

### Enable / disable lifecycle

Toggled from `/dashboard/apps/`. Enable and disable are exact mirrors —
**that symmetry is the whole point.**

**On enable:**

1. Toggle flips `PluginConfig.is_enabled` in the DB.
2. On boot the registry calls `ready()` (imperative registration) and the
   `contribute_*` methods, then `_collect_contributions` merges the results
   into the platform indexes.
3. `{% storefront_blocks "slot" %}` now finds the app's blocks
   (`storefront_blocks_for`).
4. The dashboard sidebar shows the app's pages — `plugin_context` builds
   `sidebar_sections` / `settings_sections` from `dashboard_pages()`, and
   `admin_dashboard/base.html` loops over them. No hard-coded entry anywhere.
5. The settings panel shows under its category in `/dashboard/settings/`.

**On disable** (`registry.deactivate` → `_drop_contributions`):

- Storefront blocks are dropped from the index → every `{% storefront_blocks %}`
  slot the app fed renders **empty**. Its `/dashboard/apps/<plugin>/...` and
  storefront routes 404.
- Dashboard pages leave `dashboard_pages()` → the sidebar entries **vanish**
  (the section header disappears too if it had no other pages).
- The settings panel leaves `all_settings_panels()` → its form and its
  settings-nav link **vanish**.
- Hook subscribers are not re-registered → the app stops reacting to events.

Nothing the app added survives the toggle — provided the app followed the
contract and didn't smuggle a surface into core/theme code.

**`PROTECTED_PLUGINS`.** A short tuple in
[`core/safety.py`](../core/safety.py) (`admin_dashboard`, `agent_core`,
`rbac`, `customers`) that the dashboard refuses to let you disable. These
*are* shipped as plugins (the engine is plugin-native all the way down), but
disabling one would soft-brick the install — e.g. turning off
`admin_dashboard` 404s the whole `/dashboard/`. The guard exists precisely
*because* disable genuinely removes surfaces; for these four that's
catastrophic, so they're pinned on. Everything else is freely toggleable.

> To check enabled state in code, use `app_registry.is_active("<name>")`
> (Python) or the `active_plugins` context list in templates
> (`{% if 'reviews' in active_plugins %}`). There is **no** `is_enabled()`
> method on the registry and **no** `{% plugin_enabled %}` tag yet (the tag is
> [proposed](plans/modular-os-2026-06.md)). Reading from the registry/context
> is what makes a surface auto-hide; an `{% if %}` over hard-coded markup does
> not — the markup still ships, it's just hidden.

### Two litmus tests

Every app must pass both. They're the acceptance criteria for "is this
properly modular":

1. **Delete-dir test.** `rm -rf plugins/installed/<name>/` and remove it from
   `MORPHEUS_DEFAULT_APPS` → the app is gone with **no dangling reference**.
   No other plugin, no theme, no core template names it. (Cross-plugin
   coupling goes through `core.hooks`, never a direct import — see
   [LAW 4](../RULES.md#law-4--plugins-communicate-via-hooks--outbox).)
2. **Disable test.** Toggle the app off in `/dashboard/apps/` → **every
   surface it added vanishes** — sidebar pages, settings panel, storefront
   blocks, account tiles. If any surface remains, it was hard-coded somewhere
   it shouldn't be.

### Anti-patterns — do NOT do these

Each of these welds an app's surface into code the app doesn't own, so it
**fails the disable test** — the surface outlives the toggle:

- ❌ **Hard-coding a plugin's nav into `admin_dashboard`.** Adding
  `<a href="/dashboard/apps/<plugin>/...">` to the dashboard chrome instead of
  returning a `DashboardPage`. (Even guarded by `{% if 'x' in active_plugins %}`
  it's a smell — it duplicates the `sidebar_sections` loop and the markup still
  ships. The hard-coded **affiliates** block in `base.html` is the current
  example; the fix is to verify affiliates contributes `DashboardPage`s and
  delete the block.)
- ❌ **Hard-coding a plugin's settings UI into `admin_dashboard`.** A
  `settings_<x>()` view + `if category == 'x'` dispatch instead of
  `contribute_settings_panel()`. The **payments** plugin is the current debt —
  its settings live in `admin_dashboard` and it ships **no**
  `contribute_settings_panel()`, so the panel can't follow the plugin.
- ❌ **Hard-coding a plugin's account tile/page into the storefront or a
  theme.** The **loyalty** points tile is baked into the storefront account
  view + the theme's `account_home.html`, so it survives disabling loyalty —
  the canonical violation. (It can't be done right yet — the `account_nav` /
  `account_page` slots are still [planned](plans/modular-os-2026-06.md). Until
  they land, don't add new account surfaces this way.)

See [`plans/modular-os-2026-06.md`](plans/modular-os-2026-06.md) for the full
audit of current violations and the plan to migrate each one onto a real
contribution mechanism.

---

## 6. Models, migrations, indexes

* Use `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` — see [LAW 7](../RULES.md#law-7--all-primary-keys-are-uuids).
* Use `MoneyField` from `djmoney` for currency — see [LAW 6](../RULES.md#law-6--safe-money-and-immutable-states).
* State machines use `django-fsm` `FSMField` with `@transition` decorators.
* Index every field you `filter()` on: `db_index=True` for single columns, `models.Index(fields=[…])` in `Meta` for composites.
* Run `python manage.py makemigrations <plugin>` after every model change.
* Run `python manage.py makemigrations --check --dry-run` in CI to catch missing migrations.

See [`SKILLS.md` → Add a model](../SKILLS.md#skill-add-a-model).

---

## 7. GraphQL — queries, mutations, permissions

```python
# graphql/queries.py
import strawberry
from api.graphql_permissions import has_scope, require_authenticated

@strawberry.type
class DiscountEngineQueryExtension:

    @strawberry.field(description="Discount rules visible to the caller.")
    def discount_rules(self, info: strawberry.Info) -> list[str]:
        require_authenticated(info)
        if not has_scope(info, "read:discounts"):
            return []
        # … fetch + return
        return []
```

In `app.py`:

```python
def ready(self) -> None:
    self.register_graphql_extension(
        "plugins.installed.discount_engine.graphql.queries"
    )
```

Convention: the class name **must end in `QueryExtension` or
`MutationExtension`**. The schema assembler scans for these and merges them
into the root `Query` / `Mutation` types.

### Permission helpers

| Helper | Behavior |
|---|---|
| `require_authenticated(info)` | Raises `PermissionDenied` if no session/token/agent. |
| `has_scope(info, "read:foo")` | True for an admin staff user, an API key with the scope, or an agent with the scope. |
| `current_customer(info)` | Returns the logged-in user or `None`. |
| `current_channel_id(info)` | Returns the channel id from the API key / agent — for multi-tenancy filtering. |

`PermissionDenied` is mapped to a structured GraphQL error
(`extensions.code: PERMISSION_DENIED`) by the schema extension in `api/schema.py`.

### Eager-load to avoid N+1

```python
qs = (
    Order.objects
    .select_related("customer", "channel")
    .prefetch_related("items", "items__product", "events")
)
```

Add a regression test using `assertNumQueries(...)`.

---

## 8. URLs and views

```python
# urls.py
from django.urls import path
from . import views

app_name = "discount_engine"

urlpatterns = [
    path("", views.index, name="index"),
]
```

```python
# app.py
def ready(self) -> None:
    self.register_urls(
        "plugins.installed.discount_engine.urls",
        prefix="discounts/",
    )
```

URLs land at `/discounts/` (no leading slash on the prefix; Django adds it).

### Pages vs machine endpoints (`surface=`)

A route mounted at the root is assumed to be a **page**, which means
`i18n_patterns` language-prefixes it once the store has more than one language.
That is right for `/discounts/` and wrong for a file a crawler fetches — a
sitemap has no French translation, and publishing `/fr/robots.txt` alongside
`/robots.txt` just duplicates every discovery file per language. Declare it:

```python
self.register_urls(
    "plugins.installed.my_app.urls",
    prefix="",
    surface="chrome",     # never language-prefixed
)
```

Use `surface="chrome"` for `robots.txt`, `sitemap*.xml`, `llms.txt`,
`/.well-known/*`, feeds and JSON endpoints; leave it unset for customer-facing
pages.

### Your pages and SEO

You get title, description, canonical, robots, Open Graph and structured data
for free — but only if the SEO layer can tell what your page *is*. Answer
`SEO_RESOLVE_PAGE`:

```python
def ready(self) -> None:
    self.register_hook(events.SEO_RESOLVE_PAGE, self.on_seo_resolve_page, priority=40)

def on_seo_resolve_page(self, value, request=None, context=None, **kwargs):
    # First non-None answer wins — return `value` untouched unless the URL is yours.
    if value is not None or request is None:
        return value
    match = getattr(request, "resolver_match", None)
    if getattr(match, "namespace", "") != self.name:
        return value
    # From CORE — your app must be able to describe its pages without importing
    # the seo app, which it does not depend on and which may be disabled.
    from core.seo_page import KIND_LISTING, SeoPage

    return SeoPage(kind=KIND_LISTING, subtype="lookbook", path=request.get_full_path(),
                   title=(context or {}).get("seo_title", ""), context=context or {})
```

To add properties to the JSON-LD graph for data you own (a rating, a video, a
policy), subscribe to `SEO_JSONLD_GRAPH` instead of emitting your own
`<script type="application/ld+json">` — a page carries one graph, and a second
block competes with it. Never write `<title>`, a canonical or `og:*` from a
plugin template (ADR 0036).

**If your app owns a catalogue of its own**, contribute it to `/llms.txt` and
`/llms-full.txt` through `SEO_LLMS_SECTIONS`. seo can only enumerate
`catalog.Product`, so a vertical whose listings live in its own models (a
marketplace's bookings, a venue's rooms) publishes *nothing* to AI crawlers
otherwise — and worse, seo used to emit the `## Products` heading regardless,
so the file stated the shop had an empty catalogue. Return
`[*value, {"title": "Stays", "lines": ["- [Name](url)", ...]}]`; `base` (no
trailing slash) and `full` arrive as kwargs. A section with no rows is dropped.

**If your app replaces one of the shell's routes** (the book vertical swaps
`/categories/` for `/genres/`), the shell must gate the swap on
`app_registry.is_active("<you>")` **and** whoever lists that route in the
sitemap has to gate it the same way. An ungated swap leaves every other store
301'ing a sitemap url to a route only your plugin mounts — see
`storefront/sitemap.py`.

**If your page is a private surface**, say so through `SEO_ROBOTS_RULES` rather
than asking for an edit to the seo app. `value` is a
[`core.robots.RobotsDocument`](../core/robots.py) — call `disallow()`,
`allow()` or `sitemap()` and return it. The lines apply to every crawler group.

**If your page paginates**, two things are required of you. Return `404` for a
page number past the end (Django's paginator clamps it to page 1, which turns
every integer into an indexable duplicate of your first page), and put the
paginator page in your template context as **`page_obj`** — the canonical only
trusts `?page=` when a real paginator is present, so a listing that hides its
paginator will canonicalise all of its pages onto page 1 and de-index the rest.
`?page=1` is redirected to the clean URL for you.

### Adding a card to somebody else's edit form

Products, categories, collections and CMS pages each fire a pair of events: a
filter that collects cards, and an event fired after the entity is saved. Use
them instead of editing the shell's template — a card contributed this way
disappears when your app is disabled, which an edit to `admin_dashboard` does
not.

| Entity | Filter (`value=list[dict]`) | Fired after save |
|---|---|---|
| Product | `PRODUCT_FORM_CARDS` (`product=`) | `PRODUCT_FORM_SAVED` |
| Category | `CATEGORY_FORM_CARDS` (`category=`) | `CATEGORY_FORM_SAVED` |
| Collection | `COLLECTION_FORM_CARDS` (`collection=`) | `COLLECTION_FORM_SAVED` |
| CMS page | `PAGE_FORM_CARDS` (`page=`) | `PAGE_FORM_SAVED` |

Every filter also receives `request=`, which you need if your card re-fills
itself from POST on a validation re-render. Append
`{'template': ..., 'context': {...}, 'order': int}`; the save event carries
`post=` and `files=`.

### Adding to the dashboard shell itself

Two filters cover the parts of the shell that are not a page. Both receive
`request=` and both are gated on your app being active, so what you contribute
disappears on disable — an edit to `admin_dashboard` would not.

| Filter | `value` | Renders |
|---|---|---|
| `DASHBOARD_USER_MENU` | `list[dict]` | Entries in the top-right account dropdown |
| `DASHBOARD_BODY_END` | `list[str]` | Template paths included at the end of `<body>` |

A menu entry is `{'label', 'url', 'icon', 'order', 'attrs'}` — `order` sorts,
and `attrs` is a dict of extra HTML attributes, which is how you hang a
`data-*` hook your own script binds to. `DASHBOARD_BODY_END` is the shell's
equivalent of the storefront's `global_below_body` slot: it is the only way to
ship a dialog or overlay into every dashboard page without the shell importing
you. The `feedback` app uses both — one entry, one modal.

```python
def on_user_menu(self, value, **kwargs):
    value.append({'label': 'Send feedback', 'url': '#', 'icon': 'message-square-warning',
                  'order': 50, 'attrs': {'data-feedback-open': '1'}})
    return value
```

**Your routes resolve before the app-discovery router.** Plugin URL mounts are
included most-specific-prefix first, so anything you register under
`dashboard/apps/<name>/` wins over the shell's
`apps/<str:plugin>/<slug:slug>/` discovery route — which acts as a *fallback*
for DashboardPage slugs you did not mount yourself. (Before v0.53.0 the order
was reversed and a one-segment route of your own was silently swallowed;
bookvault shipped dead endpoints that way. Guarded by
`core/tests/test_registry_url_ordering.py`.)

**Your save handler must key off something the card itself posts**, never off
the absence of a value:

```python
def on_product_form_saved(self, product=None, post=None, **kwargs):
    if not post or 'my_card_field' not in post:
        return  # the card wasn't rendered — do NOT write blanks
    ...
```

Without that check, a POST from a form that never rendered your card writes
empty values over whatever the merchant had stored. That is how the SEO panel
would have silently wiped every product's meta description and flipped noindex
pages back into the index.

---

## 9. Hooks and events

Subscribe to **built-in events** from `core.hooks.MorpheusEvents` or define
your own. Custom events should be documented as constants in your plugin so
others can subscribe.

```python
from core.hooks import MorpheusEvents

def ready(self) -> None:
    self.register_hook(MorpheusEvents.ORDER_PLACED, self.on_order, priority=80)

def on_order(self, order, **kwargs):
    # Always accept **kwargs — the signature can grow.
    # Wrap the body in try/except to keep the chain alive on bad data.
    try:
        ...
    except Exception:
        import logging
        logging.getLogger("my_plugin").warning("hook failed", exc_info=True)
```

`hook_registry.fire(event, **kwargs)` ALSO writes a row to the `OutboxEvent`
table, which the Celery `process_outbox` task drains to NATS / webhooks.
That gives you exactly-once side-effect delivery for free.

See [LAW 4 in RULES.md](../RULES.md#law-4--plugins-communicate-via-hooks--outbox).

### Sign-in plugins must respect the second-factor gate

`MorpheusEvents.AUTH_SECOND_FACTOR` (`'auth.second_factor'`) is a **filter**
fired in `core/auth/views.py:otp_verify` *after* the email-OTP succeeds and
*before* `login()` — it lets a plugin interpose a second factor by returning an
`HttpResponse` (with no subscriber the value stays `None` and login proceeds as
single-factor email-OTP). `staff_mfa` subscribes to it and redirects an enrolled
staffer to its TOTP challenge.

**If your plugin adds a new way to sign in (SSO/OIDC/SAML, magic links,
passkeys), it must route staff through the same gate** — otherwise the
alternate path silently bypasses MFA. Email-OTP fires the filter for you, but
flows that complete `login()` themselves (e.g. allauth's social login) do **not**
fire it. In that case call the single decision point directly and interpose its
response:

```python
from plugins.registry import app_registry

if app_registry.is_active('staff_mfa'):
    from plugins.installed.staff_mfa.services import second_factor_response
    mfa = app_registry.get('staff_mfa')
    resp = second_factor_response(mfa, request, user, next_url)
    if resp is not None:
        return resp   # redirect to the TOTP challenge before login completes
```

`staff_sso` does exactly this in its allauth adapter (raising
`ImmediateHttpResponse(resp)` from `pre_social_login`). Reuse
`staff_mfa.services.second_factor_response` — don't re-implement the policy —
and keep email-OTP available as the break-glass path.

---

## 10. Background tasks (Celery)

```python
# tasks.py
from celery import shared_task

@shared_task(bind=True, time_limit=120, soft_time_limit=100)
def reprice_all_products(self):
    ...
```

Always set `time_limit` + `soft_time_limit` so a runaway task can't pin a
worker forever.

To schedule it periodically:

```python
# app.py
from celery.schedules import crontab

def ready(self) -> None:
    self.register_celery_beat(
        "discount_engine.reprice_hourly",
        {
            "task": "plugins.installed.discount_engine.tasks.reprice_all_products",
            "schedule": crontab(minute=15),
        },
    )
```

---

## 11. Configuration schema

Plugins can expose a JSON Schema; the merchant admin renders it as a form.

```python
def get_config_schema(self) -> dict:
    return {
        "type": "object",
        "properties": {
            "enable_dynamic_pricing": {
                "type": "boolean",
                "default": False,
                "title": "Enable dynamic pricing",
            },
            "max_discount_pct": {
                "type": "number", "minimum": 0, "maximum": 100, "default": 30,
            },
        },
    }
```

Read values:

```python
self.get_config_value("max_discount_pct", default=30)
```

`get_config()` is cached in-process; `set_config(key, value)` invalidates the cache.

---

## 12. Multi-tenancy / channel scoping

Every business model that is per-merchant should carry a nullable FK to
`core.StoreChannel`. The platform provides:

* **In GraphQL resolvers:** `current_channel_id(info)` resolves the channel
  from the authenticated API key / agent.
* **In REST viewsets:** `request._morpheus_api_key.channel_id` is set by
  `MorpheusAPIKeyAuthentication` on every authed request.
* **For routing:** the `EnvironmentMiddleware` on the request lets you scope
  by `Environment` for dev/staging/prod.

A typical scoped queryset looks like:

```python
qs = MyModel.objects.filter(channel_id=current_channel_id(info))
```

When `channel_id` is `None`, the row applies to **all channels**.

---

## 13. Testing

### Unit / integration

```python
from django.test import TestCase

class DiscountEngineTests(TestCase):
    def test_propose_creates_pending_rule(self):
        ...
```

Run:

```bash
DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.discount_engine
```

### Permission boundary tests (mandatory)

For any authed resolver / viewset, test all three cases:

1. Anonymous → empty result or 401/403.
2. Authenticated without scope → `PERMISSION_DENIED`.
3. Authenticated with scope → sees data.

See `api/tests.py:RestPermissionTests` for the canonical pattern.

### Query-count regression

```python
with self.assertNumQueries(2):
    list(my_resolver(...))
```

---

## 14. Distribution as a community plugin

Two paths.

### Path A — drop-in via `MORPHEUS_EXTRA_APPS`

The merchant clones your plugin into `plugins/installed/<name>/` and adds
the path to:

```
MORPHEUS_EXTRA_APPS=plugins.installed.<name>
```

That's it — the plugin auto-enables on first boot.

### Path B — pip-installable

Publish your plugin as a Python package on PyPI:

```
my_morph_plugin/
├── pyproject.toml
└── my_morph_plugin/
    ├── __init__.py
    ├── apps.py
    ├── app.py
    └── ...
```

Merchants then:

```bash
pip install my-morph-plugin
```

…and add `my_morph_plugin` to `MORPHEUS_EXTRA_APPS`. The discovery
loop imports `<path>.plugin` regardless of where the package lives on disk.

**Naming convention:** prefix package names with `morph-` so they're
discoverable on PyPI.

### Shipping updates to installed copies (the per-app channel)

An app installed on its own (Path A) can be updated **without** the merchant
redeploying the platform: the publisher lists it in the signed release manifest
and the merchant's Updates page offers it. See
[`UPDATING.md` → "Updating one app or theme"](UPDATING.md#updating-one-app-or-theme-v0440).
What you, the author, must produce per release:

- a `.tar.gz` with **one** top-level directory (`my_app/` or `my_app-1.4.0/`)
  containing the app tree — `app.py` at its root, and if it has models,
  `migrations/__init__.py` (the client refuses an archive without it, because
  Django would never see the migrations);
- its `sha256`, and a `min_core` if the release needs a platform version;
- an entry in the publisher's `components.json`, signed into the manifest with
  `manage.py morph_sign_manifest --components`.

The client verifies the manifest signature, then the checksum, then inspects
the archive before it touches the installed tree; the previous version is
restored on any failure. Apps that ship with core (`MORPHEUS_DEFAULT_APPS`)
are **not** updated this way — they are part of the platform release.

---

## 15. Cookbook

### Add a custom event

```python
# In your plugin's services.py
from core.hooks import hook_registry, MorpheusEvents

# Document it as a constant for subscribers:
class DiscountEvents:
    DISCOUNT_APPLIED = "discount.applied"

# Fire it from your transition:
hook_registry.fire(DiscountEvents.DISCOUNT_APPLIED, cart=cart, amount=amount)
```

### React to an event from another plugin

```python
def ready(self) -> None:
    self.register_hook("discount.applied", self.on_discount, priority=90)

def on_discount(self, cart, amount, **kwargs):
    ...
```

### Add a Strawberry mutation that requires admin scope

```python
@strawberry.mutation(description="Create a discount rule (admin scope required).")
def create_discount_rule(self, info, input: CreateRuleInput) -> RuleType:
    require_authenticated(info)
    if not has_scope(info, "admin:discounts"):
        raise PermissionDenied("admin:discounts scope required")
    ...
```

### Schedule a daily rollup

```python
def ready(self) -> None:
    from celery.schedules import crontab
    self.register_celery_beat(
        "my_plugin.daily_rollup",
        {
            "task": "plugins.installed.my_plugin.tasks.rollup",
            "schedule": crontab(hour=0, minute=15),
        },
    )
```

### Drop into the merchant dashboard

The dashboard auto-renders **every active plugin** in its **Apps** view.
For a custom dashboard page, return a `DashboardPage` from
`contribute_dashboard_pages()` (see [§5.1](#51-modularity-contract-sdk-base)) —
the registry routes it and the sidebar lists it automatically, **and it
auto-hides when the plugin is disabled.** Prefer this over hand-mounting a URL
under `dashboard/`: a hard-coded sidebar link won't disappear on disable and
fails the litmus test.

```python
def contribute_dashboard_pages(self) -> list:
    return [DashboardPage(label='My tool', slug='tool',
                          view='plugins.installed.my_plugin.views.tool',
                          section='catalog')]
```

---

## See also

- [`THEME_DEVELOPMENT.md`](THEME_DEVELOPMENT.md) — **the Theme SDK**, the other
  half of this contract: the slots an app fills, with the canonical catalog.
- [`THEME_EXTENSIONS.md`](THEME_EXTENSIONS.md) — narrative on the slot pattern.
- [`CLAUDE.md` § Plugin contract](../CLAUDE.md) — the house rule this SDK codifies.
- [`plans/modular-os-2026-06.md`](plans/modular-os-2026-06.md) — the refactor
  finishing "disable an app → its surfaces vanish" (account slots, settings
  override, the violation audit).
- [`SKILLS.md`](../SKILLS.md) — named, repeatable procedures (the "how").
- [`RULES.md`](../RULES.md) — platform laws (the "what's non-negotiable").
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) — the "why".
- [`plugins/contributions.py`](../plugins/contributions.py) — the contribution
  dataclasses (slots / sections / categories).
- [`plugins/base.py`](../plugins/base.py) — the source of truth for the base class.
- [`plugins/registry.py`](../plugins/registry.py) — discovery + activation engine
  (`_collect_contributions` / `_drop_contributions`).
