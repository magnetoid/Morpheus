# Morpheus Framework API

The `morpheus` package is the public framework API. Plugin authors should
import everything they need from `morpheus.*` rather than reaching into
Django, the registry, or core internals.

> Django is the runtime. `morpheus` is the framework.

## Quickstart

```bash
./bin/morpheus new-plugin loyalty --with-models --with-urls
```

This scaffolds `plugins/installed/loyalty/` with a manifest, app config,
URLs, views, and a smoke test — all using `morpheus.*` imports.

## Public surface

### `morpheus`

The top-level package re-exports the things every plugin needs:

| Name                  | Purpose                                                |
| --------------------- | ------------------------------------------------------ |
| `Plugin`              | Base class for all plugins.                            |
| `DashboardPage`       | Sidebar entry on the merchant dashboard.               |
| `SettingsPanel`       | JSON-Schema-driven config form for a plugin.           |
| `StorefrontBlock`     | Template fragment rendered into a theme slot.          |
| `PluginConfigurationError` | Raised when plugin metadata fails validation.     |
| `__version__`         | Framework version string.                              |

```python
from morpheus import Plugin, DashboardPage, SettingsPanel, StorefrontBlock
```

### `morpheus.events`

Catalogue of built-in hook events. Use these constants when registering or
firing hooks so a typo crashes at import time, not at runtime.

```python
from morpheus import events

self.register_hook(events.ORDER_PLACED, self.on_order)
self.register_hook(events.CART_CALCULATE_TOTAL, self.add_shipping)  # filter
```

Available events: `ORDER_PLACED`, `ORDER_CONFIRMED`, `ORDER_PAID`,
`ORDER_CANCELLED`, `ORDER_FULFILLED`, `PAYMENT_CAPTURED`,
`PAYMENT_FAILED`, `PAYMENT_REFUNDED`, `CART_CREATED`, `CART_UPDATED`,
`CART_ABANDONED`, `CART_CALCULATE_TOTAL` (filter),
`PRODUCT_CALCULATE_PRICE` (filter), `PRODUCT_LIST_REORDER` (filter),
`PRODUCT_VIEWED`, `PRODUCT_CREATED`,
`PRODUCT_UPDATED`, `CATEGORY_UPDATED`, `CUSTOMER_REGISTERED`,
`CUSTOMER_LOGIN`, `PRODUCT_LOW_STOCK`, `PRODUCT_OUT_OF_STOCK`,
`SEARCH_PERFORMED`, `AI_DESCRIPTION_GENERATED`,
`AI_RECOMMENDATION_REQUESTED`.

Custom events are just strings — `'my_plugin.thing_happened'` works fine.

### `morpheus.hooks`

Direct access to the global hook registry for code that runs outside
`Plugin.ready()`:

```python
from morpheus import hooks

hooks.fire('order.placed', order=order)
total = hooks.filter_value('cart.calculate_total', value=base_total, cart=cart)
```

Inside `ready()` you should prefer `self.register_hook(...)`.

### `morpheus.models`

Drop-in replacement for `django.db.models`. Re-exports every public name
from Django's ORM plus `MoneyField` and `Money` from django-money.

```python
from morpheus import models

class Coupon(models.Model):
    code = models.CharField(max_length=32, unique=True)
    amount = models.MoneyField(max_digits=14, decimal_places=2,
                               default_currency='USD')
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-expires_at']
        indexes = [models.Index(fields=['code'])]
```

### `morpheus.forms`

Drop-in replacement for `django.forms`.

```python
from morpheus import forms

class CouponForm(forms.Form):
    code = forms.CharField(max_length=32)
    amount = forms.DecimalField(max_digits=12, decimal_places=2)
    expires_at = forms.DateField(required=False)

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if not code:
            raise forms.ValidationError('Code is required.')
        return code
```

### `morpheus.views`

View decorators, response classes, and shortcuts:

```python
from morpheus.views import (
    staff_required, login_required,
    render, redirect, get_object_or_404,
    HttpResponse, JsonResponse,
)

@staff_required
def my_dashboard_page(request):
    obj = get_object_or_404(MyModel, pk=request.GET['id'])
    return render(request, 'my_plugin/page.html', {'obj': obj})
```

## Building a plugin

A minimum plugin is one file:

```python
# plugins/installed/loyalty/plugin.py
from morpheus import Plugin, DashboardPage, events


class LoyaltyPlugin(Plugin):
    name = 'loyalty'
    label = 'Loyalty Points'
    version = '0.1.0'
    description = 'Award points on every order.'
    has_models = False

    def ready(self) -> None:
        self.register_hook(events.ORDER_PAID, self.on_order_paid, priority=80)

    def contribute_dashboard_pages(self):
        return [DashboardPage(
            label='Loyalty',
            slug='loyalty',
            view='plugins.installed.loyalty.views.dashboard',
            icon='star',
            section='crm',
            order=20,
        )]

    def on_order_paid(self, order, **kw):
        # Award 1 point per dollar, etc.
        ...
```

Then enable it:

```bash
./bin/morpheus enable loyalty
# Restart the server.
```

### Lifecycle

1. **Discovery** — at boot the registry imports every `plugin.py` under
   `plugins/installed/` and finds the `Plugin` subclass.
2. **Validation** — required metadata (`name`, `label`, `version`) is
   checked at class-definition time. Bad metadata crashes import; siblings
   keep loading.
3. **Activation** — for each enabled plugin (per `PluginConfig` rows),
   the registry calls `ready()` once in topologically-sorted dependency
   order (see `requires` on the plugin class).
4. **Disable** — turning a plugin off in the dashboard calls
   `on_disable()`. Override it for cleanup (delete cron entries, drop
   indexes, etc).

### Required metadata

| Field         | Required | Notes                                                    |
| ------------- | -------- | -------------------------------------------------------- |
| `name`        | yes      | snake_case, must equal the directory name.               |
| `label`       | yes      | Human-readable display name.                             |
| `version`     | yes      | SemVer-ish (e.g. `1.2.3` or `1.2.3a4`).                  |
| `description` | no       | One-line summary.                                        |
| `requires`    | no       | List of other plugin names this depends on.             |
| `conflicts`   | no       | List of plugin names that cannot coexist with this one. |
| `has_models`  | no       | `True` if the plugin defines Django models.             |

### Registration helpers (call from `ready()`)

| Method                          | What it does                                             |
| ------------------------------- | -------------------------------------------------------- |
| `register_hook(event, handler)` | Subscribe to an event (see `morpheus.events`).           |
| `register_urls(module, prefix)` | Mount a URLconf module under a prefix.                   |
| `register_graphql_extension(m)` | Add a Strawberry schema mixin.                           |
| `register_celery_tasks(module)` | Register tasks for autodiscovery.                        |
| `register_celery_beat(name, e)` | Add a periodic-task entry.                               |
| `register_context_processor(f)` | Add a template context processor.                        |

### Contribution surfaces (override the methods)

| Method                          | Returns                                                  |
| ------------------------------- | -------------------------------------------------------- |
| `contribute_dashboard_pages()`  | List of `DashboardPage` — sidebar entries.               |
| `contribute_settings_panel()`   | Single `SettingsPanel` — schema-driven config form.      |
| `contribute_storefront_blocks()`| List of `StorefrontBlock` — theme slot fragments.        |
| `contribute_agents()`           | List of `MorpheusAgent` — AI agents this plugin ships.   |
| `contribute_agent_tools()`      | List of `Tool` — capabilities the agent layer can call.  |
| `contribute_skills()`           | List of `Skill` — tool bundles for agents to opt into.   |

## CLI

```
morpheus version
morpheus list
morpheus new-plugin <name> [--with-models] [--with-urls] [--with-graphql] [--with-tasks]
morpheus new-theme <slug>
morpheus enable <plugin>
morpheus disable <plugin>
morpheus check
```

The `bin/morpheus` script wraps `manage.py morpheus`, so either form
works. Inside CI just call `python manage.py morpheus check`.

## ACP HTTP surface (Agentic Commerce Protocol)

The `agentic_checkout` plugin exposes the **Agentic Commerce Protocol**
(OpenAI/Stripe, spec version `2026-04-17`) so AI agents can discover the
catalog and build a priced checkout session against the existing `Cart`.
It is **OFF by default** (`enabled_by_default = False`) and registered in
`MORPHEUS_DEFAULT_PLUGINS`; a merchant enables it from the dashboard once
enrolled in Stripe ACP. This is distinct from — and complements — the MCP
server and the UCP/A2A `/.well-known/` discovery served by `agent_mcp`.

Every checkout-session endpoint is Bearer-authenticated and scoped to a new
`acp.checkout` scope. Unlike the MCP/GraphQL surfaces, ACP does **not**
inherit the wildcard: a token is granted access **only** when it carries an
explicit `acp_scopes` list containing `acp.checkout` (explicit grant from
**Settings → Developer → API tokens**). Each response echoes the
`API-Version: 2026-04-17` header.

| Method + path                                 | operationId            | Notes                                            |
| --------------------------------------------- | ---------------------- | ------------------------------------------------ |
| `GET /.well-known/acp.json`                   | —                      | Discovery manifest (no auth).                    |
| `GET /acp/feed.json`                          | —                      | Product feed; requires the `catalog.read` scope. |
| `POST /acp/checkout_sessions`                 | createCheckoutSession  | New `Cart` from `line_items` + `currency`.       |
| `GET /acp/checkout_sessions/{id}`             | getCheckoutSession     | Read the session.                                |
| `POST /acp/checkout_sessions/{id}`            | updateCheckoutSession  | Mutate line items / buyer / fulfillment.         |
| `POST /acp/checkout_sessions/{id}/cancel`     | cancelCheckoutSession  | Release the cart; status `canceled`.             |
| `POST /acp/checkout_sessions/{id}/complete`   | completeCheckoutSession | Money path (Phase 2) — see below.               |

The session `id` is the `Cart` id. Responses are conformant ACP
`CheckoutSession` JSON (status, currency, `line_items[]`, `totals[]`,
`capabilities`, `messages[]`, `links[]`) with amounts as integer minor
units. **`complete` is gated on the plugin's `payments_enabled` config**
(default off → `422` with a `MessageError` code `unsupported`, the Phase-1
behavior). With it on, `complete` places a real `Order` and redeems the
Stripe Shared Payment Token off-session. Money-path semantics: retrying a
completed session returns the same order (200; line items rebuilt from the
persisted Order); a concurrent completion gets a `409` with an `invalid`
"already in progress" message (retry shortly); a total that drifted since
it was quoted is refused (`422`, `param='total'` — re-fetch the session,
then retry); interrupted/processing outcomes return `422 invalid` and are
safe to retry on the **same** session (the Stripe idempotency key is
session-scoped, so a replay can never double-charge); hard declines return
`422 payment_declined` with `param='payment_data.token'` and the Stripe
decline code folded into the message content.

## When to import from Django directly

`morpheus` covers the common case. If you need something not exposed
here — Django signals, content types, custom validators, transactions,
auth user model access — keep using `django.*` imports for now. We
expand `morpheus.*` as the patterns prove worth promoting.

| Need                                     | Use                                       |
| ---------------------------------------- | ----------------------------------------- |
| Project settings                         | `from django.conf import settings`        |
| Time helpers                             | `from django.utils import timezone`       |
| Slugify                                  | `from django.utils.text import slugify`   |
| Get the user model                       | `from django.contrib.auth import get_user_model` |
| Database transactions                    | `from django.db import transaction`       |
| Field validators                         | `from django.core.validators import ...`  |
| Custom signals                           | `from django.db.models.signals import ...`|
