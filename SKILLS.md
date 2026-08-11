# SKILLS — the Morpheus build & extend playbook

This document is the **canonical procedure manual** for working on Morpheus.
Every skill below is a small, named, repeatable workflow with explicit
inputs, steps, and a validation gate. Use it like a checklist when you ship
new features, when you onboard another developer, or when you ask an AI
agent to do work in this repo.

> Skills cite source files with `[file](relative/path)` so you can jump
> straight in. When code paths drift, **update the skill file in the same
> PR** — that is part of "definition of done".

---

## How to use this file

- Each skill follows the same shape:
  ```
  ### Skill: <verb> <noun>
  **When:** trigger
  **Prereqs:** required prior skills / context
  **Steps:** numbered, executable
  **Validate:** explicit pass/fail check
  **See also:** related skills, files, docs
  ```
- Treat the **Validate** line as a gate: if it doesn't pass, the skill
  isn't done. No "I think it works."
- Skills point at **other** skills, not at long prose. If a skill needs a
  background concept, add a one-line link, don't duplicate the explanation.

---

## Map (fast index)

| Domain | Skills |
|---|---|
| [Bootstrap](#1-bootstrap--developer-environment) | run locally, run tests, run lint, reset DB |
| [Plugins](#2-plugins--the-core-extension-mechanism) | add plugin, wire hooks, expose GraphQL, register URLs, register beat schedule |
| [Models & data](#3-models--data) | add model, write migration, add index, swap to UUID PK, money fields, FSM transitions |
| [GraphQL](#4-graphql-surface) | add resolver with auth, add mutation with permission, fix N+1, error mapping, depth-limit hardening |
| [REST](#5-rest-api) | add a public-readable viewset, add an authed viewset, add scope-gated viewset |
| [Hooks & events](#6-hooks--events) | fire an event, listen to an event, write to outbox, dispatch a webhook |
| [Agents](#7-agents--ai-surface) | add an intent kind, sign a receipt, register an agent, talk to platform from the SDK |
| [Functions runtime](#8-functions-runtime) | author a function, add a capability, debug a runaway function |
| [Importers](#9-migration-importers) | add a source adapter, run a fixture-driven test, idempotent re-run |
| [Observability](#10-observability) | add a metric, query a metric, add a log line that scales, capture an error |
| [Environments](#11-environments) | snapshot, promote, rollback, gate a protected env |
| [Affiliates](#12-affiliates) | onboard an affiliate, add a commission rule, attribute an order |
| [Marketplace](#13-multivendor-marketplace) | onboard a vendor, split an order, request a payout |
| [Search](#14-semantic-search) | embed a product, query embeddings, fall back to keyword |
| [Deploy](#15-deploy--operations) | deploy to Coolify, deploy to k8s, run migrations safely, swap external DB |
| [Quality](#16-quality--ci) | add a test, add coverage, add a permission boundary test, run pre-commit |
| [Themes](#17-themes) | scaffold a theme, override a template, expose design tokens, switch active theme |

---

# 1. Bootstrap — developer environment

### Skill: run Morpheus locally
**When:** first checkout, or after pulling fresh `main`.
**Prereqs:** Python 3.12, optional Redis/Postgres for full stack.
**Steps:**
1. `python3 -m venv venv && source venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` then set `SECRET_KEY=<random>`. Leave `DATABASE_URL` empty for SQLite.
4. `python manage.py migrate`
5. `python manage.py createsuperuser`
6. `python manage.py runserver`
**Validate:** `curl http://localhost:8000/healthz` returns `{"status":"ok"}`.
**See also:** [`README.md`](README.md), [.env.example](.env.example).

### Skill: run the full test suite
**When:** before every commit, in CI, after a refactor.
**Prereqs:** dev environment.
**Steps:**
1. `DEBUG=1 SECRET_KEY=dev DATABASE_URL=sqlite:///db.sqlite3 REDIS_URL=redis://localhost:6379/0 python manage.py test --noinput`
**Validate:** prints `OK` and the number of tests run.
**See also:** [Skill: add a test](#skill-add-a-test).

### Skill: run lint + format
**When:** before pushing.
**Prereqs:** `pip install ruff mypy bandit`.
**Steps:**
1. `ruff check .`
2. `ruff format --check .`
3. `bandit -q -r . -x ./venv,./tests,./.venv -ll`
**Validate:** all three exit 0.
**See also:** [`pyproject.toml`](pyproject.toml), [`.pre-commit-config.yaml`](.pre-commit-config.yaml).

### Skill: reset local DB
**When:** schema went sideways and migrations don't replay.
**Prereqs:** Using SQLite (don't run on a shared DB).
**Steps:**
1. `rm db.sqlite3`
2. `python manage.py migrate`
3. `python manage.py createsuperuser`
**Validate:** `python manage.py check` clean and `runserver` boots without errors.

---

# 2. Plugins — the core extension mechanism

> **Rule:** if a feature can be removed and the engine still boots, it MUST
> be a plugin. See [LAW 1 in RULES.md](RULES.md#law-1--everything-is-a-plugin).

### Skill: add a new plugin
**When:** any new domain (subscriptions, gift cards, tax engine, etc.).
**Prereqs:** decide a plugin `name` (snake_case, must equal directory).
**Steps (scaffolder — recommended):**
1. `python manage.py morph_create_plugin <name> --label "Display Name" [--with-models] [--with-graphql] [--with-urls] [--with-tasks]`
2. Add `'plugins.installed.<name>'` to `MORPHEUS_DEFAULT_APPS` in [`morph/settings.py`](morph/settings.py).
3. If `--with-models`: `python manage.py makemigrations <name> && python manage.py migrate`.
4. `python manage.py check` — your plugin should appear in the activation log.

**Manual scaffold** (when you need a non-standard layout):
1. `mkdir -p plugins/installed/<name>/{graphql,migrations,tests}`
2. Create `__init__.py` setting `default_app_config = 'plugins.installed.<name>.apps.<Name>Config'`.
3. Create `apps.py` with `<Name>Config` (`name = 'plugins.installed.<name>'`, `label = '<name>'`).
4. Create `migrations/__init__.py` (empty).
5. Create `app.py` subclassing `MorpheusPlugin`. Metadata is validated at class-definition time — typos fail fast.
6. Add the path to `MORPHEUS_DEFAULT_APPS` and run migrations.

**Validate:** plugin appears in the activation log and in `Query.activePlugins`.
**See also:** [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) (full developer guide), [`plugins/base.py`](plugins/base.py), [`plugins/registry.py`](plugins/registry.py), [Skill: wire a hook listener](#skill-wire-a-hook-listener).

### Skill: wire a hook listener
**When:** the plugin needs to react to a domain event (e.g. `order.placed`).
**Prereqs:** plugin scaffold.
**Steps:**
1. In `plugin.ready()`: `self.register_hook(MorpheusEvents.ORDER_PLACED, self.on_order_placed, priority=80)`.
2. Implement `on_order_placed(self, order, **kwargs)` — keep `**kwargs` because the hook signature can grow.
3. Wrap the body in `try: ... except Exception as e: logger.warning(...) ` so a buggy plugin can't break the chain. See [`plugins/installed/marketplace/app.py`](plugins/installed/marketplace/app.py:23-29) for the canonical pattern.
**Validate:** trigger the event in a test (`hook_registry.fire('order.placed', order=order)`) and assert your handler ran.
**See also:** [`core/hooks.py`](core/hooks.py), [Skill: fire a custom event](#skill-fire-a-custom-event).

### Skill: register a GraphQL extension
**When:** plugin exposes queries / mutations.
**Prereqs:** module path of a class named `<X>QueryExtension` or `<X>MutationExtension`.
**Steps:**
1. Create `<plugin>/graphql/queries.py` (and/or `mutations.py`). Define a class `class <Plugin>QueryExtension:` decorated with `@strawberry.type`.
2. In `plugin.ready()`: `self.register_graphql_extension('plugins.installed.<name>.graphql.queries')`.
3. Restart server (schema is built at `AppConfig.ready` — see [`api/apps.py`](api/apps.py)).
**Validate:** `MUTATION FIELDS` / `QUERY FIELDS` log line shows your new fields.
**See also:** [Skill: add a resolver with auth](#skill-add-a-resolver-with-auth).

### Skill: register plugin URLs
**When:** plugin owns its own HTTP routes (storefront views, redirect endpoints).
**Steps:**
1. `<plugin>/urls.py` with `urlpatterns = [...]` and `app_name = '<name>'`.
2. In `plugin.ready()`: `self.register_urls('plugins.installed.<name>.urls', prefix='', namespace='<name>')`.
**Validate:** `python manage.py show_urls | grep <name>` lists the route.
**See also:** [`plugins/installed/affiliates/urls.py`](plugins/installed/affiliates/urls.py).

### Skill: register a Celery beat schedule
**When:** plugin needs periodic tasks (rollups, sweeps, backfills).
**Steps:**
1. Create the task in `<plugin>/tasks.py` with `@shared_task(bind=True, time_limit=…, soft_time_limit=…)`.
2. In `plugin.ready()` mutate `CELERY_BEAT_SCHEDULE`. See [`plugins/installed/observability/app.py`](plugins/installed/observability/app.py).
3. `setdefault(...)` so a merchant override wins.
**Validate:** `celery -A morph beat -l debug` logs the schedule entry.

---

# 3. Models & data

### Skill: add a model
**When:** every new domain entity.
**Prereqs:** plugin scaffold.
**Steps:**
1. Use `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` ([LAW 7](RULES.md#law-7--all-primary-keys-are-uuids)).
2. Money columns → `MoneyField` ([LAW 6](RULES.md#law-6--safe-money-and-immutable-states)).
3. State machines → `FSMField` from `django_fsm` and `@transition` decorators.
4. `class Meta`: `ordering`, `indexes` — at minimum index every field you `filter()` on.
5. `python manage.py makemigrations <plugin>`.
**Validate:** `python manage.py makemigrations --check --dry-run` says no changes needed.
**See also:** [`plugins/installed/orders/models.py`](plugins/installed/orders/models.py), [Skill: add an index](#skill-add-an-index).

### Skill: add an index
**When:** queries get slow OR adding a new query path.
**Steps:**
1. For a single column queried with `=`/`IN`: `db_index=True` on the field.
2. For a composite filter: `class Meta: indexes = [models.Index(fields=['a', '-b'])]`.
3. `makemigrations` to capture.
**Validate:** `EXPLAIN ANALYZE` (Postgres) shows the index used.

### Skill: change a model safely
**When:** non-additive schema change (rename, drop, retype).
**Steps:**
1. Plan a **two-PR** path: PR-A adds the new column + dual-writes, PR-B removes the old column.
2. Always pair with a `data` migration when the new column has computed defaults.
3. Run `python manage.py migrate --plan` to read out the plan before deploying.
**Validate:** rolling back the migration locally restores the old schema cleanly.

---

# 4. GraphQL surface

### Skill: add a resolver with auth
**When:** new readable field.
**Prereqs:** plugin GraphQL extension registered.
**Steps:**
1. Inside `@strawberry.type class XQueryExtension:` define `@strawberry.field def my_field(self, info, …) -> T:`.
2. At the top of the resolver call `require_authenticated(info)` from [`api/graphql_permissions.py`](api/graphql_permissions.py).
3. If scope-gated: `if not has_scope(info, 'read:my_thing'): return []` (or raise `PermissionDenied`).
4. Eager-load: `select_related('a','b').prefetch_related('c')` — see [Skill: fix N+1](#skill-fix-n1).
**Validate:** an unauthenticated request gets 401-equivalent or empty list; a wrong-scope agent gets `PERMISSION_DENIED`.
**See also:** [`plugins/installed/orders/graphql/queries.py`](plugins/installed/orders/graphql/queries.py).

### Skill: add a mutation with permission
**Steps:**
1. `@strawberry.mutation def do_thing(self, info, input: …Input) -> …Type:`.
2. Authenticate first, then validate input length / shape, then call into a service. **Never put business logic in the resolver.**
3. Map domain errors to `PermissionDenied` / standard exceptions; the schema extension in [`api/schema.py`](api/schema.py) converts them to `code: PERMISSION_DENIED`.
**Validate:** test that an unauthenticated caller sees `errors[0].extensions.code == 'PERMISSION_DENIED'`.
**See also:** [`plugins/installed/ai_assistant/graphql/mutations.py`](plugins/installed/ai_assistant/graphql/mutations.py).

### Skill: fix N+1
**When:** a list resolver returns objects whose nested fields each issue a query.
**Steps:**
1. Identify which fields are accessed downstream (look at the GraphQL type definition).
2. Add `select_related(*foreign_keys)` for FK access; `prefetch_related(*reverse_or_m2m)` for the rest.
3. For aggregations: `annotate()` rather than per-row arithmetic.
4. Add a regression test using `assertNumQueries(...)`.
**Validate:** the test passes after, fails before.
**See also:** [`plugins/installed/catalog/graphql/queries.py`](plugins/installed/catalog/graphql/queries.py).

### Skill: tighten depth / alias limits
**When:** fielding suspicious traffic or before opening to the public.
**Steps:**
1. Lower `GRAPHQL_MAX_QUERY_DEPTH` and `GRAPHQL_MAX_ALIASES` in [`morph/settings.py`](morph/settings.py).
2. `MorpheusGraphQLView._validate_complexity` already reads from settings — no code changes.
**Validate:** a too-deep query returns 400 with `Query exceeds maximum depth of N`.

---

# 5. REST API

### Skill: add a public-readable viewset
**When:** storefront-style data, no auth required.
**Steps:**
1. Subclass `viewsets.ReadOnlyModelViewSet`.
2. `permission_classes = [permissions.AllowAny]` (override the project default `IsAuthenticated`).
3. `get_queryset()` filters out non-public rows (status, channel scoping).
**Validate:** `curl /v1/<resource>/` returns 200 anonymously.
**See also:** [`api/rest.py`](api/rest.py).

### Skill: add an authed viewset
**Steps:**
1. Inherit project default permissions (no `permission_classes` override → `IsAuthenticated`).
2. In `get_queryset()` scope to the requesting principal: `request.user`, `request._morpheus_api_key`, or `request.agent_capabilities`.
**Validate:** unauthenticated request gets 401/403; authenticated user sees only their rows.

### Skill: gate a route by scope
**Steps:**
1. `from core.authentication import HasScopePermission`.
2. `permission_classes = [HasScopePermission.for_scope('write:invoices')]`.
**Validate:** a key without the scope returns 403.

---

# 6. Hooks & events

### Skill: fire a custom event
**When:** new domain transition that other plugins should be able to react to.
**Steps:**
1. Add a constant to `MorpheusEvents` in [`core/hooks.py`](core/hooks.py).
2. Call `hook_registry.fire('your.event', subject=foo, **other_kwargs)` from inside the service that performs the transition.
3. Document the payload shape in the constant's docstring.
**Validate:** a downstream plugin can subscribe and receive the kwargs.

### Skill: ensure a side-effect survives crashes
**When:** the side-effect must happen exactly once even on retry.
**Steps:**
1. Within the same `transaction.atomic()` block as the domain change, call `hook_registry.fire(...)`. The fire writes an `OutboxEvent`.
2. The Celery task `core.tasks.process_outbox` drains and publishes to NATS / webhooks.
**Validate:** crash the worker mid-publish; on restart, the event still appears in the downstream subscriber.
**See also:** [`core/tasks.py`](core/tasks.py:73-117), [LAW 4](RULES.md#law-4--plugins-communicate-via-hooks--outbox).

### Skill: dispatch a remote webhook
**Steps:**
1. Create a `WebhookEndpoint` (admin) with `events=['order.placed']` and a `secret`.
2. Receivers verify with `core.tasks.verify_hmac_signature(secret, request.body, request.headers['X-Morpheus-Signature'])`.
**Validate:** the round-trip test in [`api/tests.py`](api/tests.py) (`WebhookSignatureTests`) passes.

---

# 7. Agents & AI surface

### Skill: register an agent
**Steps:**
1. Create an `AgentRegistration` row (admin or API). The `signing_secret` auto-generates.
2. Decide capabilities: `can_browse`, `can_purchase`, `can_manage_inventory`. Set a `budget_limit_amount` if money is in play.
3. Distribute the `token` to the agent owner; keep the `signing_secret` private (used to verify receipts).
**Validate:** the agent can call `Query.ping` on `/graphql/agent/` with `Authorization: Bearer <token>`.

### Skill: add a new intent kind
**When:** a new agent-driven workflow (e.g. `subscribe`, `gift`, `bulk_order`).
**Steps:**
1. Add a tuple to `AgentIntent.KIND_CHOICES` in [`plugins/installed/ai_assistant/models.py`](plugins/installed/ai_assistant/models.py).
2. Map it to a capability in `_KIND_TO_CAPABILITY` in [`services/intent.py`](plugins/installed/ai_assistant/services/intent.py).
3. `makemigrations` (the choices list change is captured on the field).
4. Add a lifecycle test (proposed → authorized → executing → completed).
**Validate:** `intent_service.propose(agent=…, kind='your_kind')` succeeds for a capable agent and raises `CapabilityDenied` otherwise.

### Skill: build & verify a receipt
**When:** an intent completes; you want a tamper-proof audit record.
**Steps:**
1. `intent_service.complete(intent, result={...}, actual_cost=Money(...))`.
2. The service writes the receipt + signature to the AgentIntent row and emits `agent.intent.completed` on the event bus.
3. Consumers verify with `verify_receipt(payload, signature, agent.signing_secret)` from [`receipts.py`](plugins/installed/ai_assistant/services/receipts.py).
**Validate:** tampering with `result` fails verification.

### Skill: talk to Morpheus from the SDK
**Steps:**
1. `pip install -e services/sdk_python`.
2. `from morph_sdk import MorphAgentClient` and instantiate with `base_url`, `agent_token`, optional `signing_secret`.
3. Use `agent.search_products(...)`, `agent.propose_intent(...)`, `agent.list_my_intents(state=…)`.
**Validate:** the SDK happy-path test in `services/sdk_python/tests/` passes (or hand-run against the dev server).

---

# 8. Functions runtime

> **Threat model:** the Functions runtime is "merchant-managed" — gate writes
> to the model in the admin/API. It is *not* a hostile-code sandbox.

### Skill: author a Function
**Steps:**
1. Decide a `target` from `Function.TARGET_CHOICES` (e.g. `cart.calculate_total`).
2. Source must define `def run(input): ...` and return either `None` (no change) or the new value.
3. Declare `capabilities = ['math', 'money']` to opt into curated globals.
4. Set `priority` (lower runs first when multiple Functions hit the same hook).
5. Test via the GraphQL `testRunFunction` mutation before enabling.
**Validate:** `is_enabled=True` and the next domain event shows the function in `FunctionInvocation` with `success=True`.
**See also:** [`plugins/installed/functions/runtime.py`](plugins/installed/functions/runtime.py), [Skill: add a runtime capability](#skill-add-a-runtime-capability).

### Skill: add a runtime capability
**When:** Functions need access to a new safe primitive (e.g. `currency`, `date`).
**Steps:**
1. In [`runtime.py`](plugins/installed/functions/runtime.py) call `register_capability('mycap', {'today': lambda: datetime.utcnow().date(), ...})`.
2. Audit the exports for hostile use (no file, no network, no globals access).
3. Document the capability in this file under [Skill: author a Function](#skill-author-a-function).
**Validate:** a Function declaring `capabilities=['mycap']` resolves the names; without the capability it raises.

### Skill: debug a runaway Function
**Steps:**
1. Check `FunctionInvocation` for the latest row — `error_message` is your first signal.
2. If `success=True` but the value is wrong, run via `testRunFunction` with the same input.
3. If timeouts: bump `timeout_ms` (default 200ms; hard kill at 4×).
**Validate:** Function's `last_error` clears after the next successful invocation.

---

# 9. Migration importers

### Skill: add a source adapter
**When:** new commerce platform to migrate from (Magento, BigCommerce, …).
**Steps:**
1. Create `plugins/installed/importers/adapters/<source>.py`. Subclass `BaseImporter` with `source = '<key>'`.
2. Implement `iter_products`, `iter_customers`, `iter_orders` — accept either an HTTP client or an offline `records` dict (so tests don't hit the network).
3. Each `_import_X` method must `self.upsert(source_id=…, dest_obj=…)` so re-runs are idempotent.
4. Register the adapter in [`management/commands/morph_import.py`](plugins/installed/importers/management/commands/morph_import.py).
**Validate:** a fixture-driven test runs the importer twice and the second run creates 0 new rows.
**See also:** [`adapters/shopify.py`](plugins/installed/importers/adapters/shopify.py), [`adapters/woocommerce.py`](plugins/installed/importers/adapters/woocommerce.py).

### Skill: import from a JSON fixture (offline)
**Steps:**
1. Build a JSON file matching the source's API shape: `{"products": [...], "customers": [...], "orders": [...]}`.
2. `python manage.py morph_import shopify --from-file=fixtures/shopify.json`.
**Validate:** the run finishes with non-zero counts and zero errors in `ImportRun`.

---

# 10. Observability

### Skill: add a metric
**When:** a new domain event is worth tracking on the dashboard.
**Steps:**
1. Add an entry to `_EVENT_METRIC_MAP` in [`plugins/installed/observability/services.py`](plugins/installed/observability/services.py).
2. The `rollup` task auto-populates `MerchantMetric` rows on the next beat tick.
3. Expose it via the existing `metricSeries` GraphQL field (no schema change needed — it accepts any metric name).
**Validate:** `Query.supportedMetrics` returns your metric; querying the series after a beat tick returns at least one bucket.

### Skill: query a metric
**Steps:**
1. `Query.metricSeries(metric: "orders_placed", granularity: "hour", hours: 24)` from any agent or admin client.
2. Requires `read:metrics` scope.
**Validate:** the response contains `points` with `bucket`, `value`, `sample_count`.

### Skill: log with structure
**When:** any log line in the engine.
**Steps:**
1. `logger.info('cart_repriced', extra={'cart_id': cart.id, 'subtotal': subtotal})` — pass IDs as `extra`, never interpolate raw PII.
2. Errors get `exc_info=True`. Always.
3. Don't log `Authorization`, agent tokens, or Stripe secrets — see the (planned) `before_send` scrubber in [`morph/settings.py`](morph/settings.py).
**Validate:** Loki / your log aggregator can filter on the field.

### Skill: capture an error for the merchant dashboard
**Steps:**
1. `from plugins.installed.observability.services import record_error`.
2. `record_error(source='payments', message=str(e), stack_trace=traceback.format_exc(), channel=channel)`.
**Validate:** the row appears in `ErrorEvent` and renders in the merchant dashboard.

---

# 11. Environments

### Skill: snapshot an environment
**Steps:**
1. `from plugins.installed.environments.services import take_snapshot`.
2. `snap = take_snapshot(env, label='pre-launch', actor=user)`.
**Validate:** `snap.payload` carries `theme_overrides` and `settings_overrides`.

### Skill: promote dev → production
**Steps:**
1. Take a snapshot of dev.
2. `promote(snapshot=snap, target=prod, confirm=True, note='ship X')`.
3. Without `confirm=True` on a `is_protected=True` environment, the call raises `PermissionError`.
**Validate:** target environment now has the snapshot's overrides; a `Deployment` row exists with `status='applied'` and a `diff`.

### Skill: rollback a bad deploy
**Steps:**
1. Find the deployment: `Deployment.objects.filter(target__slug='production').order_by('-started_at').first()`.
2. `rollback(deployment)`.
**Validate:** target reverts to the pre-deploy state; the `Deployment.status` becomes `rolled_back`.

---

# 12. Affiliates

### Skill: onboard an affiliate
**Steps:**
1. Affiliate program (admin): `AffiliateProgram(commission_type='percent', commission_value=10, cookie_window_days=30)`.
2. Affiliate row created on application; merchant sets `status='approved'`.
3. The affiliate creates one or more `AffiliateLink`s via `Mutation.createAffiliateLink(input)`.
**Validate:** `Query.myAffiliateLinks` returns the link; visiting `/r/<code>` redirects + sets the `morph_aff` cookie.

### Skill: attribute an order
**Steps:**
1. Storefront writes the affiliate code into the order (`order.shipping_address['affiliate_code']` or `order.source = 'affiliate:<code>'`).
2. The plugin's `order.placed` listener calls `attribute_order(order, code)`.
**Validate:** an `AffiliateConversion` exists for the order; affiliate's `accrued_balance` increases when the conversion is approved.

---

# 13. Multivendor marketplace

### Skill: onboard a vendor
**Steps:**
1. `VendorApplication` (admin) → review → set `status='approved'`.
2. Promote to `catalog.Vendor` (manual or via a future automation hook).
3. Configure `Vendor.commission_rate` and create a `VendorPayoutAccount`.
**Validate:** vendor's products appear in the catalog; an order containing them generates a `VendorOrder` on placement.

### Skill: split an order
**When:** automatic on `order.placed`.
**Manual:** call `split_order(order)` from [`marketplace/services.py`](plugins/installed/marketplace/services.py).
**Validate:** one `VendorOrder` per distinct vendor; sums of `gross` equal the order subtotal; `commission` matches the configured rate.

### Skill: pay a vendor
**Steps:**
1. `request_vendor_payout(vendor=…, amount=Money(…), method='ach')` creates a pending `VendorPayout`.
2. After paying out externally, call `mark_vendor_payout_paid(payout, external_reference=…)`.
**Validate:** vendor's `accrued_balance` decreases by exactly `amount`; `lifetime_paid` increases; payout `status='paid'`.

---

# 14. Semantic search

### Skill: embed a product
**When:** `product.created` / `product.updated` (auto via Celery), or manual backfill.
**Manual:** `from plugins.installed.ai_assistant.services.search import upsert_product_embedding` then `upsert_product_embedding(product)`.
**Validate:** `ProductEmbedding.objects.filter(product=product).exists()` and `dim > 0`.

### Skill: query embeddings
**Steps:**
1. `Query.semanticSearch(query: "blender under 80", first: 8)`.
2. The response includes `usedEmbedding` — `True` only when there are existing rows AND the query embedded successfully.
**Validate:** result count is non-zero; `usedEmbedding=True` after an embedding pass.

### Skill: backfill embeddings for an existing catalog
**Steps:**
1. `python manage.py shell -c "from plugins.installed.ai_assistant.tasks import refresh_product_embedding; from plugins.installed.catalog.models import Product; [refresh_product_embedding.delay(str(p.id)) for p in Product.objects.filter(status='active')]"`.
**Validate:** tail the worker logs; row count in `ProductEmbedding` should grow toward the active product count.

---

# 15. Deploy & operations

### Skill: deploy to Coolify
**Steps:**
1. + New Resource → Docker Compose → repo `magnetoid/morpheus`, branch `main`.
2. Compose file is the default `docker-compose.yml` — don't override.
3. Paste env from [`.env.coolify.example`](.env.coolify.example); set `SECRET_KEY`, Stripe + LLM keys.
4. Bind a domain to the `web` service. Deploy.
**Validate:** `https://<domain>/healthz` returns ok; admin login works after `python manage.py createsuperuser` via Coolify terminal.
**See also:** [`docs/deploy-coolify.md`](docs/deploy-coolify.md).

### Skill: run a one-off migration in prod
**Steps:**
1. Coolify → web container terminal → `/app/scripts/docker-entrypoint.sh migrate`.
2. Or as a pre-deploy hook: `docker compose run --rm web migrate`.
**Validate:** `python manage.py showmigrations` shows the latest migration applied.

### Skill: swap to an external Postgres
**Steps:**
1. Comment out the `postgres` service in [`docker-compose.yml`](docker-compose.yml).
2. Set `DATABASE_URL=postgres://…` in env.
3. Re-deploy.
**Validate:** `/readyz` returns 200; `python manage.py dbshell` works.

### Skill: run the full local stack
**Steps:**
1. `docker compose -f docker-compose.dev.yml up -d`.
**Validate:** Grafana on `:3000`, Prometheus on `:9090`, Loki on `:3100`, app on `:8000`.

---

# 16. Quality & CI

### Skill: add a test
**When:** every new behavior. Period.
**Steps:**
1. Locate the right `tests/` package next to the code (`plugins/installed/<plugin>/tests/`).
2. Subclass `django.test.TestCase`. Use `setUp()` for fixtures.
3. Test the *behavior*, not the implementation. Example: assert that the receipt verifies, not that the function was called.
**Validate:** the test fails when you delete the new behavior, passes when it's there.

### Skill: add a permission boundary test
**When:** any new authed resolver / viewset.
**Steps:**
1. Three cases: anonymous, wrong-scope authenticated, right-scope authenticated.
2. Assert anonymous gets `[]` or 401/403; wrong-scope gets `PERMISSION_DENIED` or 403; right-scope sees data.
**See also:** [`api/tests.py:RestPermissionTests`](api/tests.py).

### Skill: run pre-commit hooks
**Steps:**
1. `pip install pre-commit && pre-commit install`.
2. `pre-commit run --all-files` once to baseline.
**Validate:** subsequent commits run ruff + bandit + secret-detection automatically.

### Skill: keep CI green
**Trip-wires:** missing migrations, lint failures, test failures, large-file commits.
**Steps:**
1. `python manage.py makemigrations --check --dry-run` before pushing.
2. `ruff check . && ruff format --check .`.
3. `DATABASE_URL='sqlite:///:memory:' python manage.py test --noinput` (bare `manage.py test` reads the Docker `db` host from `.env` and hangs outside the container).
**Validate:** GitHub Actions run on the PR is green. (CI billing on the account must be active.)

---

# 17. Themes

> Full theming guide at [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md).
> Themes override templates and ship design tokens; they do **not** run business logic.

### Skill: scaffold a new theme
**When:** designing a new storefront look.
**Steps:**
1. `python manage.py morph_create_theme <name> --label "Display Name" [--from dot_books]`
2. `export MORPHEUS_ACTIVE_THEME=<name>` (or update `morph/settings.py`).
3. `python manage.py check` — your theme should appear in the activation log as `Active theme: <name>`.
4. `python manage.py runserver` and open `/`.
**Validate:** `theme_registry.active.name == "<name>"` and the home page renders your `templates/storefront/home.html`.
**See also:** [`themes/management/commands/morph_create_theme.py`](themes/management/commands/morph_create_theme.py).

### Skill: override a single template
**When:** swap one storefront page (e.g. a custom home) without rewriting the rest.
**Steps:**
1. Create the file at `themes/library/<name>/templates/storefront/<page>.html` — same path as the plugin template you want to replace.
2. Use `{% extends "storefront/base.html" %}` to inherit the theme's shell.
3. Restart server (templates are template-loader cached).
**Validate:** the route renders your override; `git diff` shows only one new file.

### Skill: expose design tokens
**When:** every theme should declare its palette + type + radii so the dashboard editor (and future CSS-var export) works.
**Steps:**
1. Implement `get_design_tokens()` in `theme.py` — see the dot books theme for the canonical example.
2. Mirror the tokens in your CSS as `:root { --<token>: <value> }` so a future export can swap them.
**Validate:** `theme_registry.active.get_design_tokens()` returns a non-empty dict.

### Skill: switch the active theme at runtime
**When:** A/B test or per-channel theming.
**Steps:**
1. Persist a `themes.ThemeConfig(theme_name=…, is_active=True)` row.
2. Call `theme_registry.set_active_from_db()` (it reads ThemeConfig first, falls back to settings).
**Validate:** the storefront renders the new theme on the next request.

### Skill: gate a theme on required plugins
**When:** your theme uses templates that only make sense if a particular plugin is active (e.g. a `marketplace/vendor_card.html`).
**Steps:**
1. Set `requires_plugins = ["marketplace"]` on your `MorpheusTheme` subclass.
2. Run `theme_registry.validate_active_theme()` — it will return an error string if the plugin isn't active.
**Validate:** disable the plugin temporarily; the validation surface complains. Re-enable; clean.

---

## Appendix — file pointers

| Concept | Where |
|---|---|
| Plugin base + registry | [`plugins/base.py`](plugins/base.py), [`plugins/registry.py`](plugins/registry.py) |
| Hook bus + outbox | [`core/hooks.py`](core/hooks.py), [`core/tasks.py`](core/tasks.py) |
| GraphQL view + permission helpers | [`api/graphql_view.py`](api/graphql_view.py), [`api/graphql_permissions.py`](api/graphql_permissions.py), [`api/schema.py`](api/schema.py) |
| Authentication | [`core/authentication.py`](core/authentication.py), [`api/permissions.py`](api/permissions.py) |
| Webhook signing helpers | [`core/tasks.py`](core/tasks.py) (`compute_hmac_signature`, `verify_hmac_signature`) |
| Settings (DEBUG/CORS/throttles) | [`morph/settings.py`](morph/settings.py) |
| Default compose (production) | [`docker-compose.yml`](docker-compose.yml) |
| Full dev stack compose | [`docker-compose.dev.yml`](docker-compose.dev.yml) |
| Coolify deploy guide | [`docs/deploy-coolify.md`](docs/deploy-coolify.md) |
| Platform laws | [`RULES.md`](RULES.md) |
| Architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Strategic vision | [`AI_VISION.md`](AI_VISION.md) |

---

## Definition of done

Before opening a PR, every change satisfies:

- [ ] **A skill in this file points at it** (or a new skill is added in the same PR).
- [ ] Tests pass locally + cover the new behavior.
- [ ] `python manage.py check` and `makemigrations --check --dry-run` clean.
- [ ] No broad `except Exception` without `exc_info=True` and a one-line reason.
- [ ] If the change touches deploy: [`docs/deploy-coolify.md`](docs/deploy-coolify.md) updated.
- [ ] If the change touches docs: index entries here are still accurate.
