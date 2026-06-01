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
├── plugin.py            ← MorpheusPlugin subclass
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
# 1. Add 'plugins.installed.discount_engine' to MORPHEUS_DEFAULT_PLUGINS in morph/settings.py
# 2. Generate the migration:
python manage.py makemigrations discount_engine
python manage.py migrate

# 3. Verify:
python manage.py check                # plugin appears in the activation log
python manage.py test plugins.installed.discount_engine
```

That's it — the plugin is live.

---

## 2. Anatomy of a plugin

```
plugins/installed/<name>/
├── __init__.py             # default_app_config -> apps.<NameConfig>
├── apps.py                 # Django AppConfig (label = <name>)
├── plugin.py               # ★ MorpheusPlugin subclass: the manifest
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

The **only required file** is `plugin.py`. Everything else is opt-in.

---

## 3. The lifecycle

```
                ┌──────────────────────────────────────────────┐
                │            settings.py boot                  │
                │ MORPHEUS_DEFAULT_PLUGINS + EXTRA_PLUGINS     │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │ plugin_registry.discover(paths)              │
                │   imports each <plugin>.plugin module        │
                │   discovers MorpheusPlugin subclass          │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │ plugin_registry.activate_all()  (AppReady)   │
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
| `has_models` | `bool` | ✅ if you have models | If True, the plugin needs to be in `INSTALLED_APPS`. |

The base class **validates** all metadata at class-definition time — typos
fail fast at import, not at runtime.

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

The four contribution surfaces an app may use:

| Surface | Method | Lands in | Auto-removed on disable? |
|---|---|---|---|
| **Storefront block** | `contribute_storefront_blocks()` | a theme slot via `{% storefront_blocks "slot" %}` | ✅ |
| **Dashboard page** | `contribute_dashboard_pages()` | merchant sidebar (main or settings nav) | ✅ |
| **Settings panel** | `contribute_settings_panel()` | `/dashboard/settings/<category>/` form | ✅ |
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

> To check enabled state in code, use `plugin_registry.is_active("<name>")`
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
   `MORPHEUS_DEFAULT_PLUGINS` → the app is gone with **no dangling reference**.
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

In `plugin.py`:

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
# plugin.py
def ready(self) -> None:
    self.register_urls(
        "plugins.installed.discount_engine.urls",
        prefix="discounts/",
    )
```

URLs land at `/discounts/` (no leading slash on the prefix; Django adds it).

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
# plugin.py
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
python manage.py test plugins.installed.discount_engine
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

### Path A — drop-in via `MORPHEUS_EXTRA_PLUGINS`

The merchant clones your plugin into `plugins/installed/<name>/` and adds
the path to:

```
MORPHEUS_EXTRA_PLUGINS=plugins.installed.<name>
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
    ├── plugin.py
    └── ...
```

Merchants then:

```bash
pip install my-morph-plugin
```

…and add `my_morph_plugin` to `MORPHEUS_EXTRA_PLUGINS`. The discovery
loop imports `<path>.plugin` regardless of where the package lives on disk.

**Naming convention:** prefix package names with `morph-` so they're
discoverable on PyPI.

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
