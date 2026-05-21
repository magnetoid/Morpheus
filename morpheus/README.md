# `morpheus` — the public Python SDK

> The contract third-party plugin authors build against. Importing from `morpheus` (not from `core/`, not from `plugins/installed/<other_plugin>/`, not from Django internals) is how plugins stay forward-compatible across major Morpheus versions.
>
> **Stability:** the symbols documented here are stable within a major version. See [`../docs/API_STABILITY.md`](../docs/API_STABILITY.md) for the full surface map + deprecation policy.

---

## Why this layer exists

The plugin contract in [`CHARTER.md` §5](../CHARTER.md#5-the-plugin-contract) says: a plugin imports from `morpheus`, not from `core/` or `django.*`. The reason is simple — Django, Strawberry, and the platform internals change. The SDK absorbs those changes so a plugin written in 2026 keeps working in 2028.

Concretely:

```python
# DON'T — couples your plugin to Django + our private layout.
from django.db import models
from django.http import HttpResponse
from plugins.base import MorpheusPlugin
from plugins.contributions import DashboardPage
from core.hooks import hook_registry, MorpheusEvents

# DO — single namespace, contract-bound.
from morpheus import Plugin, DashboardPage, events, hooks
from morpheus.models import Model, MoneyField
from morpheus.views import HttpResponse, render, staff_member_required
```

---

## What's in the SDK

### Top-level (`from morpheus import …`)

| Symbol | Role |
|---|---|
| `Plugin` | Base class for every plugin's `plugin.py`. Subclass it, set `name`/`label`/`version`/`requires`, optionally implement `ready()`, `contribute_dashboard_pages()`, `contribute_storefront_blocks()`, `contribute_settings_panel()`. |
| `DashboardPage` | Contribution dataclass — `(label, slug, view, icon, section, order)`. Returned from `contribute_dashboard_pages()`. Mounted automatically at `/dashboard/apps/<plugin>/<slug>/`. |
| `StorefrontBlock` | Contribution dataclass — declares a block slot the active theme can render via `{% storefront_blocks "slot_name" %}`. |
| `SettingsPanel` | Contribution dataclass — adds a configuration form to `/dashboard/settings/<category>/`. |
| `PluginConfigurationError` | Raise from `ready()` to refuse activation with a clear message; the registry isolates the failure so siblings keep loading. |
| `__version__` | The currently-installed Morpheus version. Use to gate `requires` in your plugin manifest. |

### Submodules

| Module | Purpose | Common uses |
|---|---|---|
| `morpheus.events` | Canonical hook event names. `ORDER_PAID`, `PRODUCT_VIEWED`, `CART_ABANDONED`, etc. | `self.register_hook(events.ORDER_PAID, self.on_paid, priority=80)` |
| `morpheus.hooks` | Global hook registry — for firing events from service code outside `ready()` | `hook_registry.fire(events.MY_EVENT, payload=...)` |
| `morpheus.models` | Django ORM re-exports + `MoneyField` | `class Subscription(Model): price = MoneyField(...)` |
| `morpheus.forms` | Django form primitives — `Form`, `ModelForm`, `CharField`, etc. | Standard form authoring |
| `morpheus.views` | View decorators + HTTP helpers — `render`, `staff_member_required`, `HttpResponse`, `JsonResponse`, `redirect`, `csrf_protect`, `require_http_methods` | Standard view authoring |

---

## A minimal plugin (the full canonical example)

```python
# plugins/installed/hello/plugin.py
from morpheus import Plugin, DashboardPage, events

class HelloPlugin(Plugin):
    name = 'hello'
    label = 'Hello World'
    version = '0.1.0'
    description = 'The smallest possible Morpheus plugin.'
    has_models = False
    requires = ['catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.hello.urls',
            prefix='dashboard/apps/hello/',
            namespace='hello',
        )
        self.register_hook(events.ORDER_PAID, self.on_paid, priority=80)

    def contribute_dashboard_pages(self):
        return [DashboardPage(
            label='Hello',
            slug='index',
            view='plugins.installed.hello.views.index',
            icon='heart',
            section='apps',
            order=10,
        )]

    def on_paid(self, order, **_):
        # Side-effecting handler. Money paths must stay sync; see RULES.md §7.
        self.log.info('order %s paid', order.order_number)
```

```python
# plugins/installed/hello/views.py
from morpheus.views import HttpResponse, staff_member_required, render

@staff_member_required
def index(request):
    return render(request, 'hello/index.html', {'active_nav': 'apps'})
```

```python
# plugins/installed/hello/apps.py
from django.apps import AppConfig
class HelloConfig(AppConfig):
    name = 'plugins.installed.hello'
    label = 'hello'
    default_auto_field = 'django.db.models.BigAutoField'
```

That's the whole minimum. The plugin contract spec lives in [`CHARTER.md` §5](../CHARTER.md#5-the-plugin-contract).

---

## Hook events — the public catalogue

`morpheus.events` exposes every event the platform fires. The full list is in [`morpheus/events.py`](events.py). The most-commonly-subscribed:

| Event | Fires when | Args |
|---|---|---|
| `ORDER_PLACED` | Cart → Order transition succeeded | `order=` |
| `ORDER_PAID` | Payment confirmed (Stripe webhook idempotent) | `order=` |
| `ORDER_CANCELLED` | Order moved to cancelled state | `order=` |
| `ORDER_FULFILLED` | All items shipped | `order=` |
| `PAYMENT_CAPTURED` | Money moved | `payment=` |
| `PAYMENT_FAILED` | Gateway returned a permanent failure | `payment=`, `reason=` |
| `PAYMENT_REFUNDED` | Full or partial refund issued | `payment=`, `amount=` |
| `CART_ABANDONED` | Cart inactive 60+ min after last interaction | `cart=` |
| `ADD_TO_CART` / `REMOVE_FROM_CART` | Live cart edits | `cart=`, `item=`, `product=`, `quantity=` |
| `BEGIN_CHECKOUT` | Customer entered the checkout funnel | `cart=` |
| `PRODUCT_VIEWED` | PDP rendered | `product=`, `customer=` (optional), `session_key=` (optional) |
| `PRODUCT_CREATED` / `PRODUCT_UPDATED` | Catalog mutation | `product=` |
| `PRODUCT_LOW_STOCK` / `PRODUCT_BACK_IN_STOCK` | Inventory crossing thresholds | `product=`, `variant=` |
| `CUSTOMER_REGISTERED` / `CUSTOMER_LOGIN` | Account events | `customer=` |
| `SEARCH_PERFORMED` | Storefront search ran | `query=`, `results_count=`, `customer=` (optional) |
| `CART_CALCULATE_TOTAL` / `CART_CALCULATE_BREAKDOWN` | **Filter** events — handlers transform the running total | `value=` (chain through) |
| `PRODUCT_CALCULATE_PRICE` | **Filter** event — adjust per-product price (dynamic pricing) | `value=`, `product=`, `customer=` |

`fire(...)` events are best-effort fan-out — all handlers run, exceptions are isolated.
`filter(...)` events thread a value through the handler chain — each handler returns the (possibly transformed) value.

### Registering with priority + async mode

```python
self.register_hook(events.ORDER_PAID, self.fire_ga4, priority=95, mode='async')
self.register_hook(events.ORDER_PAID, self.decrement_stock, priority=80, mode='sync')
```

`priority`: lower number runs first. `mode='async'`: handler runs in a Celery worker after the request returns (use for analytics, embeddings, marketing emails — anything not in the critical path). `mode='sync'` (default): handler runs in-request.

---

## What's NOT in `morpheus`

Intentional non-exports:

- **`django.db.models.Model` directly** — go through `morpheus.models.Model`. The SDK can swap the ORM layer in the future.
- **`strawberry`** — GraphQL extensions register through `Plugin.register_graphql_extension(module_path)` so the schema-stability checker can diff additions.
- **Cross-plugin internals** — there is no `from morpheus.catalog import Product`. Talk to the catalog plugin through GraphQL or hooks. Cross-plugin direct imports break the dependency rule in [`CHARTER.md` §4](../CHARTER.md#4-layered-architecture).
- **`HttpRequest`-based session/cookie internals** — go through `morpheus.views`'s decorators which handle the cross-cutting concerns (CSRF, request_id, agent context).

---

## Versioning + stability promise

The symbols in this README are stable within a major version. Specifically:

- **No removals without a deprecation cycle.** A symbol stays callable through one major version after it's marked `@deprecated`.
- **Additions are backwards-compatible.** New events, new contribution types, new SDK utilities — all safe.
- **Field-set on dataclasses** (`DashboardPage`, `StorefrontBlock`, `SettingsPanel`) — new optional fields are safe; required-field changes are major.
- **Hook event names + arg keywords** — frozen. Renaming `ORDER_PAID` or its `order=` kwarg requires a major version + 1-year deprecation window.

Full policy: [`docs/API_STABILITY.md`](../docs/API_STABILITY.md). Charter-level policy: [`CHARTER.md` §7](../CHARTER.md#7-whats-stable-what-isnt).

---

## When something's missing

If you reach for a `core/` or `django.*` import inside a plugin, **stop**. Three things to do, in order:

1. **Check** whether the symbol you want belongs in the SDK. If a third-party plugin author needs it, it does.
2. **Open an issue** tagged `sdk-gap` describing the use case. The maintainer team adds the symbol to `morpheus.*` with a stability commitment.
3. **In the meantime**, you can reach into private APIs — but those imports will break at the next major release, and your plugin will need an update. Mark them with `# TODO(sdk): replace with morpheus.<symbol> when it lands`.

---

## Source

The SDK is intentionally thin. Re-exports + a few utilities. The interesting code lives behind the contract:

- [`__init__.py`](__init__.py) — top-level exports
- [`events.py`](events.py) — canonical hook event names
- [`hooks.py`](hooks.py) — global registry façade
- [`models.py`](models.py) — Model + MoneyField + common fields
- [`forms.py`](forms.py) — form primitives
- [`views.py`](views.py) — view decorators + HTTP helpers

Reading these tells you the entire public surface in <500 lines.
