# Morpheus OS — Comprehensive Code Analysis & Improvement Recommendations

> **Date:** 2026-06-12
> **Scope:** Complete codebase analysis (1,465 .py files, 60+ plugins, core/api/themes)
> **Method:** Three parallel deep-dive sweeps (core+api, plugins, testing+CI/CD+DevOps)
> **Source-of-truth:** All findings are observation-only; no changes made.

---

## Executive Summary

| Severity | Count | Key Themes |
|---|---:|---|
| **HIGH** | 53 | Plugin contract violations, missing tests on critical paths, god modules, security gaps, missing CI gates |
| **MEDIUM** | 70 | Cross-plugin coupling, missing abstractions, performance hotspots, observability gaps |
| **LOW** | 55 | Code style, docstring gaps, naming consistency, dead code |

**Overall Health:** **B+** — strong architectural foundation (modular, hooks bus, safety boundary, agent layer) with concentrated debt in: (1) `core/` reaching into plugin models (56 sites, violating the documented plugin contract); (2) test coverage (53% of plugins have 0 tests, including GDPR-critical `customers`); (3) CI/CD gaps (no mypy invocation, no CVE scan, no SBOM, no end-to-end tests); (4) god modules needing decomposition (`core/agents/llm.py`, `core/assistant/runtime.py`).

---

## 1. Critical Architecture Issues (HIGH severity)

### 1.1 God Modules Needing Decomposition

| Module | Lines | Responsibilities Mixed | Refactor Strategy |
|---|---:|---|---|
| `core/agents/llm.py` | 660+ | Provider protocol + retry + JSON repair + context-window + per-provider HTTP | Split into `core/agents/llm/{base,providers/{openai,anthropic,ollama,openai_compatible}}.py` |
| `core/assistant/runtime.py` | 600+ | `Assistant` class owns prompt build + persistence + dispatch + retry + SSE shaping | Extract `_run_provider_attempt`, `_dispatch_tool_calls`, `_persist_turn`, `_shape_final_event` |
| `api/graphql_view.py` | 326 | Bearer auth + depth validation + cache headers + AST tag extraction + edge TTL | Split into `api/graphql/{auth,depth,cache_headers,ast_tags}.py` |
| `core/assistant/apply.py` | 300+ | `apply_proposal` + `preflight` + git plumbing in one module | Extract `GitStep` chain; `preflight` gates as list of callables |
| `core/hooks.py` | 500+ | `MorpheusEvents` 200+ line magic-string catalogue | Extract `events.py` schema; auto-validate kwargs; generate typed payloads |

**Impact:** Blocking gunicorn workers for 4+ minutes on slow LLM calls (SSE thread holds request thread). **Quick fix:** wrap `provider.respond()` in per-call timeout via `concurrent.futures`.

### 1.2 Plugin Contract Violations (56 cross-plugin imports from `core/`)

The contract says: *core → plugin imports (wrong direction)*. Reality:

| File | Cross-plugin imports | Severity |
|---|---:|---|
| `core/agents/llm.py` | 9 sites to `ai_assistant.services.config` | HIGH |
| `core/assistant/tools/ecommerce.py` | 15 sites to orders/catalog/inventory/cms/media/metafields/markets | HIGH |
| `core/assistant/tools/ecommerce_writes.py` | 10 sites to agent_core/orders/catalog/metafields/cms | HIGH |
| `core/assistant/tools/{admin_ops,spawn,database,logs}.py` | 12 sites | HIGH |
| `core/i18n/agent_tools.py` | 2 sites to catalog | MEDIUM |
| `core/context_processors.py` | 2 sites to orders.Cart | MEDIUM |
| `api/{rest,exception_handler,graphql_view,permissions,llm_tasks,schema}.py` | 18 sites | MEDIUM |

**Pattern:** All use the same `try: from plugins.installed.X.models import ...; except Exception: pass` idiom.

**Fix (long-term):** Migrate to `contribute_agent_tools()` pattern — each plugin owns its own tools (e.g. `orders.cancel(order_id, reason)`), core/assistant/tools/* only contains meta tools.

**Fix (quick):** Wrap all 56 sites in `core.imports.lazy_model("catalog.Product")` helper — buys headroom for the proper migration.

### 1.3 Missing Abstraction Layers

| Need | Current State | Proposed |
|---|---|---|
| **Principal abstraction** | Auth-resolver code duplicated 4× across `api/graphql_view.py`, `api/permissions.py`, `api/middleware.py`, `api/llm_tasks.py` | `core/auth/principal.py` with `Principal` NamedTuple; `current_principal(request)` |
| **Cache key helper** | `f'...:{id}'` hand-rolled in 6 files | `core/cache_keys.py` with `rate_limit_key()`, `idempotency_key()` |
| **AI provider config** | `core/agents/llm.py` reaches into `ai_assistant` directly | `core.agents.providers.get_config()` thin shim with plugin-registry default |

### 1.4 `LLMMessage` Fallback — Latent Circular Import Risk

`core/assistant/runtime.py:163-174` defines a fallback `LLMMessage` dataclass inside a function because the canonical import is fragile. **Fix:** Move to `core/agents/messages.py` (no Django imports). Runtime depends on that, not the full agents kernel.

---

## 2. Plugin Health Issues

### 2.1 Plugin Contract Gaps

| Issue | Plugin | Fix |
|---|---|---|
| **No `apps.py`** | `storefront`, `ai_content` | Add `class StorefrontConfig(AppConfig)` mirroring `shipping/apps.py` |
| **Deprecated `default_app_config`** | `linda_generated/apps.py:24` | Remove (Django 5.x compatibility landmine) |
| **Pokes private registry API** | `linda_generated/apps.py:16-17` | Use `plugin_registry.register_class()` |
| **Returns model in wrong file** | `orders/models.py:367-369` re-exports `ReturnRequest` from `refunds.py` | Move `ReturnRequest` to `models.py`; lazy-import service into `refunds.py` |
| **Forward reference with `# noqa: F821`** | `orders/refunds.py:131` | Resolved by above move |
| **CMS reaches into theme** | `cms/plugin.py:67-74` | Theme registers its own sections via `ready()` hook |

### 2.2 GDPR-Critical Plugin With Zero Tests (HIGH)

**`plugins/installed/customers/`** — owns Customer model, LTV rollups, data-export + anonymise flows. 5 migrations, **0 tests**. The `anonymise_customer` function reaches into 7 sibling plugins (orders, reviews, consent, wishlist, loyalty_points, affiliates, payments) and swallows all ImportErrors with bare `except Exception: pass`.

**Fix:** Block any GDPR-touching merge without a test. Add `tests/test_anonymise_customer.py` and `tests/test_update_cdp_metrics.py`. Target 80% coverage of `services.py`.

### 2.3 25 Plugins With Models But Zero Tests

| Plugin | Risk |
|---|---|
| **marketing** (2 migrations) | Coupon model affects every cart |
| **webhooks_ui** (2 migrations) | Critical integration surface |
| **returns_portal** (2 migrations) | Refund touchpoint |
| **tracking** (2 migrations) | Analytics + ad pixels |
| **workflows** (2 migrations) | State machines |
| **b2b** (1 migration) | Net 15/30/45 invoicing |
| **gift_cards** (1 migration) | Money — append-only ledger |
| **promotions** (1 migration) | Rule engine with stacking |
| **rbac** (1 migration) | Permission boundary itself |
| **consent** (1 migration) | GDPR/EEA surface |
| + 15 more | |

**Fix:** CI gate — every plugin that ships a model must ship at least one test. Scaffold via `morph_create_plugin` already generates `tests/test_smoke.py`.

### 2.4 File Handle Leaks (HIGH)

```python
# plugins/installed/digital_products/views.py:90
# plugins/installed/seo/views.py:312, 316
response = FileResponse(open(abs_path, 'rb'), as_attachment=True, filename=filename)  # noqa: SIM115
```

The `noqa` silences the linter. If the response errors between `open` and `return`, the FD leaks.

**Fix:**
```python
with open(abs_path, 'rb') as f:
    return FileResponse(f, as_attachment=True, filename=filename)
```

### 2.5 CSRF Audit on Storefront POST Endpoints

`storefront/views/cart.py:36, 77` and checkout endpoints handle payment state transitions. They rely on global CSRF middleware but have no explicit `csrf_protect` — an AJAX-cart refactor mistake could add `csrf_exempt` and break the protection.

**Fix:** Audit all storefront POST views. Never use `@csrf_exempt` on storefront endpoints. Document the rule in `docs/PLUGIN_DEVELOPMENT.md`.

### 2.6 `loyalty_points/services.py:60` is_authenticated Default-True Bug

```python
if customer is None or not getattr(customer, 'is_authenticated', True): return
```

The `getattr` defaults to `True` when missing. If `customers.Customer` is a custom model without `is_authenticated`, **guest orders earn loyalty points**.

**Fix:** Replace with explicit type check or `isinstance(customer, AbstractBaseUser)`.

### 2.7 N+1 in Critical Paths (HIGH)

| Location | Issue | Fix |
|---|---|---|
| `orders/dashboard.py:55-81` | 4 separate aggregate queries for KPI panel | Combine 2× 14-day series into one `TruncDate` aggregate |
| `orders/dashboard.py:135` | `Order.objects.exists()` per setup step | 60s cache wrapper |
| `tax/services.py:118`, `affiliates/services.py:422`, etc. | Unannotated loops over `order.items.all()` | `qs.select_related('product', 'variant').prefetch_related(...)` |
| `media/views.py:402, 667` | `MediaAsset.objects.all()` no prefetch | `select_related('folder', 'uploader').prefetch_related('tags')` |
| `ai_assistant/plugin.py:106-110` | Python sort after DB order_by | Add `priority_rank` field; `order_by` at DB level |

### 2.8 Unauthenticated Download with No Rate Limit (HIGH)

`digital_products/views.py:29-91` — `download` is unauthenticated by design (token = credential), but no rate-limit on `download` itself. A leaked token can drain `max_downloads` in parallel burst from many IPs.

**Fix:** Add `check_and_consume` rate-limit (10/min/IP). Use `select_for_update()` for the `downloads_used += 1` increment.

---

## 3. Security Findings

### 3.1 Sandbox Can Be Hosed by Runaway Script (HIGH)

`core/agents/sandbox.py:171-180` uses `threading.Thread` with timeout. **Python threads cannot be forcefully killed** — timed-out thread runs forever, leaks FDs, eventually OOMs.

**Fix:** Replace with `multiprocessing.Process` + `terminate()` or subprocess with `preexec_fn`. This is the only real DoS vector in the read code.

### 3.2 XSS Risk in Markdown Template Tag (MEDIUM)

`core/templatetags/morph.py:246`: `mark_safe(markdown_to_html(value))` — the markdown library is the only barrier. If it ever returns unescaped HTML, this is an XSS sink.

**Fix:** Add integration test asserting `<script>` in markdown source is escaped/removed.

### 3.3 Stripe Webhook Rate-Limit Bypassable (MEDIUM)

`payments/views.py:36-37`:
```python
ip = request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR', 'unknown')
```

If not actually fronted by Cloudflare, attacker spoofs `CF-Connecting-IP` to bypass.

**Fix:** Use `REMOTE_ADDR` only (Django's `MIDDLEWARE` should set this after the proxy strips spoofable headers).

### 3.4 Bare `except: pass` Masks Real Failures (HIGH)

30+ sites in `core/` and `api/`, plus `orders/refunds.py:248-249` and `orders/services.py:96, 98, 128` swallow all exceptions. If a downstream service regresses, the dashboard bell or order confirmation email silently never arrives.

**Fix:** Replace `pass` with `logger.warning(..., exc_info=True)`. Reserve silent `pass` for explicitly optional hooks (and even then log at DEBUG).

### 3.5 OutboxEvent Not in `on_commit` (MEDIUM)

`core/hooks.py:248-258` — `OutboxEvent.objects.create` + `dispatch_webhook.delay` is not wrapped in `transaction.on_commit`. If the request rolls back, you have an outbox event referencing a transaction that never existed.

**Fix:** Move outbox creation inside `transaction.on_commit`.

### 3.6 `anonymise_customer` Leaves Race Conditions (HIGH)

`customers/services.py:285-389` — after anonymise, `email` is replaced with `deleted-<uuid>@dotbooks.invalid`, but `username` and `id` remain. New signups with the same email address could collide (if `unique=True` on email). Transactional email services keep the old address in their lists.

**Fix:** After anonymising, also call `customer.emailaddress_set.all().delete()`, `customer.socialaccount_set.all().delete()`, and fire `CUSTOMER_ANONYMISED` event.

---

## 4. Performance Findings

### 4.1 Context Processor Hits DB Every Request (MEDIUM)

`core/context_processors.py:30-52`:
- `cart.first()` + `item_count` on every request
- `current_channel(request)` called twice per request

**Fix:** Cache per `user.id`/`session_key` for 15-30s with `cache.get_or_set`. Memoize `current_channel` via `request._morpheus_channel`.

### 4.2 `_graphql_edge_ttl` Re-evaluated Every Request (MEDIUM)

`plugins/registry.py:225-237` — called on every GraphQL response. Cache per-process.

### 4.3 Streaming SSE Blocks Request Thread 4+ Minutes (MEDIUM)

`core/assistant/runtime.py:306-329` — provider call is sync. With 8 steps × 30s providers × 1s retry, can hold a gunicorn worker indefinitely.

**Fix:** Wrap in `async` (Django 4+ supports it) or run in Celery worker and stream via Redis pubsub.

### 4.4 Sync-Fallback Runs Webhooks in Request (MEDIUM)

`core/hooks.py:139-148` — async-fallback runs handler in the request when Celery is down. 5-minute Celery outage = every webhook fires synchronously.

**Fix:** Add deadline/timeout to the sync-fallback.

---

## 5. Testing & CI/CD Gaps

### 5.1 mypy Installed But Never Invoked (HIGH)

`ci.yml:32` installs `mypy==1.13.0`, `pyproject.toml` has a full `[tool.mypy]` config with `warn_unused_ignores`, `warn_redundant_casts`, `check_untyped_defs` — and the `lint` job **never runs `mypy`**.

**Fix:** Add `mypy morph core plugins` to the `lint` job; gate on `mypy --no-incremental`.

### 5.2 Coverage Floor Is 40% (HIGH)

`ci.yml:110` sets `coverage report -m --fail-under=40`. For a payments-critical 60+ plugin platform, 40% is permissive and unlikely to ever block a regression.

**Fix:** Tighten to 70%, add per-file `--fail-under=60`, publish to Codecov with status check on PR diff.

### 5.3 No CVE Scan (HIGH)

No `pip-audit`, `osv-scanner`, or `safety` in CI. `requirements.txt` has unpinned `>=` for every dep. A known CVE in any of `openai`, `stripe`, `anthropic`, `pillow`, `sentry-sdk`, `PyGithub` ships unblocked.

**Fix:** Add `pip-audit --strict --requirement requirements.txt` to lint job; fail on any vulnerability.

### 5.4 No Container Image Scan (HIGH)

`cd.yml` does no Trivy/Grype/Docker Scout scan before push to GHCR. No `cosign` signature, no SLSA provenance.

**Fix:** Add `anchore/scan-action` (or `aquasecurity/trivy-action`) before push; fail on CRITICAL/HIGH.

### 5.5 CD Has No Deploy Smoke Test (HIGH)

`cd.yml` builds and pushes the image — but does not deploy. The repo's only deploy path is "Coolify watches the repo" (every `git push` is implicitly a deploy). No canary, no manual-approval gate, no smoke test, no rollback.

**Fix:** Add a `smoke` job that runs `docker run … curl /healthz`; tag `:prod` only on green; add `rollback` job pinned to previous `:prod` image.

### 5.6 No End-to-End / Browser / Load Tests (HIGH)

No `tests/e2e/`, no Playwright config, no Selenium/cypress, no `locust`/`k6`/`vegeta`. Nothing covers: full purchase flow (cart → checkout → Stripe webhook → order placed → email), agent invoke path, affiliate split-payout.

**Fix:** Add Playwright E2E for critical user journeys; add `locust` for load test of checkout + webhook path.

### 5.7 No Renovate / Dependabot (MEDIUM)

`requirements.txt` is unpinned. `verify_deps.sh` hook is local-only. CI has no equivalent.

**Fix:** Add `dependabot.yml` (pip ecosystem, weekly, `pip-compile` PRs); add `dependency-review-action` to CI PR job.

### 5.8 No Scheduled CI (MEDIUM)

No `cron:` trigger in any of the 4 workflows. No weekly full-suite run, no `pip-audit`/`safety`/`osv-scanner` cron, no `bandit -r` regression sweep.

**Fix:** Add `.github/workflows/weekly.yml` with `on.schedule: cron: '0 5 * * 1'`.

### 5.9 `pytest-django` Installed But Unused (MEDIUM)

`ci.yml:108` runs `coverage run --source='.' manage.py test --noinput` — **Django's unittest runner, not pytest**, despite the install.

**Fix:** Add `[tool.pytest.ini_options]` block, root `conftest.py`, switch CI to `pytest --cov` with `pytest-xdist` for parallelism.

### 5.10 Pre-commit Hooks Not Enforced in CI (MEDIUM)

`.pre-commit-config.yaml:1` is the only standard integration. Maintainer who skips `pre-commit install` lands a green build with all 4 pre-commit checks bypassed.

**Fix:** Add `pre-commit` job to `ci.yml` that runs `pre-commit run --all-files` on every PR.

### 5.11 Lighthouse + Accessibility Hit Prod, Fail Deploys (MEDIUM)

`lighthouse.yml:6` and `accessibility.yml:50` run against `https://dotbooks.store/` on every push to `main`. A Lighthouse flake (LCP 2.6s vs 2.5s budget) **fails the production deploy**.

**Fix:** Run against preview deploy, or move to weekly `cron` with manual override.

---

## 6. Code Smells & Maintainability

### 6.1 Long Functions (>100 lines)

| Function | Lines | Module | Refactor |
|---|---:|---|---|
| `Assistant.stream` | 195 | `core/assistant/runtime.py:255-449` | Split into 5 named methods |
| `_extract_entity_tags` | 92 | `api/graphql_view.py:148-239` | Extract `TAG_MAP` constant + `visit()` |
| `on_dashboard_panels` | 38 | `ai_assistant/plugin.py:101-138` | Extract `insights_top4()`, `pulse_top5()`, `ai_summary_dict()` |

### 6.2 Magic Numbers

| Location | Value | Suggested constant |
|---|---|---|
| `core/assistant/views.py:108` | `message[:10_000]` | `MAX_MESSAGE_CHARS` |
| `core/assistant/runtime.py:276, 358` | `message[:50_000]` ×2 | Constant |
| `api/llm_tasks.py:97-105` | `1000, 4096, 0.6, 2.0, 0.0` | `MAX_TOKENS_HARD`, `DEFAULT_TEMPERATURE` |
| `api/rate_limit.py:32, 36, 38, 46` | `600, 100, 60, 120` | `AGENT_LIMIT`, `ANON_LIMIT`, `WINDOW_SECONDS` |
| `api/idempotency.py:56` | `timeout=86400` (24h) | `_IDEMPOTENCY_TTL_SECONDS` |

### 6.3 Duplicate Code Patterns

| Pattern | Sites | Fix |
|---|---:|---|
| `try: from plugins.installed.X.models import ...; except: pass` | 56 | `core/imports.lazy_model("X.Y")` helper |
| `try: Decimal(str(x)); except: return` | 4 | `core.utils.money.to_decimal(value, default=Decimal('0'))` |
| Auth-resolver dance (read `request.user`, `request._morpheus_api_key`, `request.agent_capabilities`) | 4 | `core.auth.principal.current_principal(request)` |
| `_retriable` needle-list for AI provider errors | 2 | Move to `core/agents/llm.py`; reuse |

### 6.4 Stale Prose Plugin Counts

README says "60+ active" in 5 places; actual `MORPHEUS_DEFAULT_PLUGINS` has 84 entries. CLAUDE.md "Living document" rule explicitly warns about this.

**Fix:** Replace with "see `MORPHEUS_DEFAULT_PLUGINS`" everywhere; add `scripts/check_plugin_counts.py` CI check.

### 6.5 Missing Test Infrastructure

- No `Makefile` / `justfile` for `make dev/test/lint/format/typecheck/migrate/seed`
- `core/tests.py` is literally `# Create your tests here.`
- `_test_settings_tmp.py` is a hidden landmine at repo root
- No shared `factories.py` — 60+ plugins each roll their own `Customer.objects.create_user()`
- No `pytest.ini` / `conftest.py` / `setup.cfg`
- 19 plugins ship no `tests/` directory at all
- 30+ plugins have empty `tests/__init__.py` with no `test_*.py`

---

## 7. Documentation Gaps

| Doc | Gap |
|---|---|
| `docs/OPERATIONS_RUNBOOK.md` | 37 lines for a "merging to main = prod" stack — no incident response, no rollback procedure, no secret rotation |
| `docs/adr/` | References "ADR 0011" and "ADR 0014" in prose but no discoverable artifacts |
| `CHANGELOG.md` | Hand-edited; no `release-please` / `conventional-changelog` automation |
| `docs/accessibility.md` | Single page; passing axe ≠ WCAG compliance |
| `SECURITY.md` | No GitHub Security Advisories setup, no `.github/ISSUE_TEMPLATE/security.md` |
| Plugin manifests | Inconsistent docstring quality — some 1-line, some 5-line |

---

## 8. Top 15 Highest-Leverage Fixes (by ROI)

| # | Severity | Fix | Effort | Impact |
|---|---|---|---|---|
| 1 | HIGH | Add `pytest-django` + conftest + pytest in CI | 1 PR | Halves test runtime; opens xdist + factory_boy + parametrize |
| 2 | HIGH | Turn on `mypy` in CI | 1 PR | Catches type regressions currently silenced |
| 3 | HIGH | Add `pip-audit` + `trivy` + `gitleaks` to CI/CD | 1 PR | Closes CVE/scan gap in one go |
| 4 | HIGH | Test `customers/services.py` to 80% coverage | 1 PR | GDPR-critical, zero tests today |
| 5 | HIGH | Replace `threading.Thread` with `multiprocessing.Process` in sandbox | 1 PR | Closes the only real DoS vector |
| 6 | HIGH | Add `apps.py` to `storefront` + `ai_content`; remove `default_app_config` from `linda_generated` | 1 PR | Plugin contract compliance |
| 7 | HIGH | Replace 30+ `except: pass` with `logger.warning(..., exc_info=True)` | 1 PR | Surfaces silent failures |
| 8 | HIGH | Wrap `FileResponse(open(...))` in `with` blocks (3 files) | 1 PR | Closes FD leak |
| 9 | HIGH | Add `scripts/check_plugins_have_tests.py` CI gate | 1 PR | Closes 19-plugin test gap |
| 10 | MEDIUM | Migrate `customers/services.py` cross-plugin imports to `core.hooks` subscribers | 1 PR | Resolves the architectural debt |
| 11 | MEDIUM | Extract `Principal` abstraction; collapse 4 auth-resolver duplicates | 1 PR | Removes dead code; clarity |
| 12 | MEDIUM | Move `LLMMessage` to `core/agents/messages.py` | 30 min | Removes latent boot fragility |
| 13 | MEDIUM | Cache `current_channel` + `cart_item_count` in context processor | 1 PR | Removes per-request DB hits |
| 14 | MEDIUM | Combine 2× 14-day aggregates in `orders/dashboard.py` | 1 PR | One query, not two; on hot path |
| 15 | MEDIUM | Add `Makefile` / `justfile` for `dev/test/lint/format/typecheck` | 1 PR | Universal Python DX shortcut |

---

## 9. Code That's Already Strong (credit)

| Surface | Why it works |
|---|---|
| `core/safety.py` | Layered enforcement (PROTECTED_PATHS, PROTECTED_PLUGINS) is exemplary; `assert_diff_safe` is the gold standard for AI-touchable code |
| `core/agents/registry.py` | Clean registry with `_tool_owners`, `drop_plugin()`; correctly mutates dict-while-iterating |
| `core/hooks.py` | Handler isolation (line 102-112, 165-175) is well-tested-by-design; `WebhookEncoder` strips `HttpRequest` to prevent session-data leaks |
| `core/money.py` | Small, focused, every helper quantises — good example of "one rule per function" |
| `core/assistant/codegen.py` | AST scanner is a strong defence against LLM-generated code smuggling `mark_safe`/`eval`/`os.system` into proposals |
| `core/i18n/`, `core/embeddings.py` | Translation kernel + embedding provider abstraction with deterministic-hash fallback (tests work without API keys) |
| `morph/settings.py` MIDDLEWARE ordering | Documented (262-265) — exemplary |
| `api/llm_tasks.py:130-156` | 404 (not 403) on owner mismatch — anti-enumeration |
| `core/safety.py:46-49` | Correctly enumerates `morph/urls.py` and `wsgi.py` as protected |
| Plugin registry | Fail-soft per-plugin activation (registry.py:164-176); topological-sort |
| `plugins/contributions.py` | `slots=True` dataclasses (no dict bloat) |
| `api/rest.py:73-83, 107` | Correct `select_related`/`prefetch_related` usage |
| `core/request_id.py` | Canonical pattern, well-implemented |
| `core/security_headers.py` | Wired correctly |

---

## 10. Recommended Implementation Order

### Phase 1: Foundation (1-2 weeks)
- Fix HIGH #5 (sandbox DoS), #8 (FD leaks), #7 (silent exceptions), #6 (plugin contract gaps)
- Add test infrastructure (#1 pytest, #9 test gate)
- Turn on CI gates (#2 mypy, #3 CVE/scan, #10 weekly cron)

### Phase 2: Architecture (2-4 weeks)
- Decompose god modules (LLMMessage move, Principal abstraction, lazy import helper)
- Migrate `customers/services.py` to `core.hooks` subscribers
- Add `apps.py` to storefront/ai_content
- Resolve `orders/models.py` re-export

### Phase 3: Test Coverage (4-6 weeks)
- Test all 25 plugins with models but no tests
- Add E2E tests for critical flows (checkout, webhook, agent invoke)
- Add load tests for hot paths (dashboard, checkout)

### Phase 4: Observability & DX (2-3 weeks)
- Add CD smoke test, canary, rollback
- Container signing (cosign)
- Replace 40% coverage floor with 70% + Codecov
- Add Makefile, CODEOWNERS, PR template

### Phase 5: Documentation (1-2 weeks)
- Backfill ADRs (0011, 0014, new ones)
- Expand `OPERATIONS_RUNBOOK.md` to incident-response playbooks
- Add `docs/deploy-k8s.md` (Coolify is single point of failure)

---

## 11. Files Read in Detail (for traceability)

### Core + API
- `core/safety.py`, `core/hooks.py`, `core/models.py`, `core/money.py`
- `core/assistant/{views,runtime,apply,codegen,persistence,prompts,providers,modes,urls,tasks,_mock_provider,models}.py`
- `core/assistant/tools/{ecommerce,ecommerce_writes,database,filesystem,admin_ops,code}.py`
- `core/agents/{llm,runtime,sandbox,base,tools,policies,memory,registry,events,trace,skills,prompts}.py` + `core/agents/builtin/worker.py`
- `core/audit/{services,models}.py`, `core/auth/{models,services,views}.py`
- `core/errors/{services,middleware,views}.py`, `core/i18n/{services,agent_tools}.py`
- `core/context_processors.py`, `core/security_headers.py`
- `api/{views,rest,permissions,rate_limit,idempotency,exception_handler,llm_tasks,middleware,cache,graphql_view,graphql_permissions}.py`

### Plugins
- `plugins/base.py`, `plugins/registry.py`, `plugins/contributions.py`
- All 78 `plugins/installed/*/plugin.py` manifests
- All 78 `plugins/installed/*/apps.py` (where present)
- `plugins/installed/catalog/{plugin.py,models.py,signals.py,image_pipeline.py}`
- `plugins/installed/orders/{plugin.py,models.py,refunds.py,services.py,dashboard.py,signals.py,store_credit.py}`
- `plugins/installed/payments/{plugin.py,models.py,views.py,urls.py,gateway.py}`
- `plugins/installed/inventory/{plugin.py,models.py,services.py,views.py,cart_reservations.py}`
- `plugins/installed/customers/services.py`
- `plugins/installed/ai_assistant/{plugin.py,__init__.py}`
- `plugins/installed/linda_generated/{plugin.py,apps.py}`
- `plugins/installed/digital_products/views.py`
- `plugins/installed/personalisation/services.py`
- `plugins/installed/loyalty_points/services.py`
- `plugins/installed/b2b/plugin.py`

### CI/CD + DevOps
- `.github/workflows/{ci,cd,lighthouse,accessibility}.yml`
- `.pre-commit-config.yaml`, `.dockerignore`, `Dockerfile`
- `docker-compose.yml`, `docker-compose.dev.yml`
- `pyproject.toml`, `requirements.txt`, `manage.py`
- `morph/settings.py`, `scripts/docker-entrypoint.sh`
- `services/ops_agent/main.py`
- `docs/{OPERATIONS_RUNBOOK,PERFORMANCE,QUICK_START,accessibility,SKILLS}.md`
- `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`

### Greps performed
- `from plugins.installed.*.models import` (60+ matches)
- `select_related`/`prefetch_related` usage across all plugins
- `raw()/RawSQL/extra()` (none in core/api)
- `FileResponse(open())` (3 sites)
- `csrf_exempt` (1 site — payments webhook, correct)
- `default_app_config` (1 site — linda_generated)
- `except: pass` and `# noqa: BLE001, S110` patterns (~30 sites)
- `.exists()` on hot paths
- model `Meta` / `Index` audit (50+ models)

---

**Bottom line:** Morpheus has a strong architectural foundation (plugin contract, hooks bus, safety boundary, agent layer) and the right instincts (fail-soft plugin loading, crash isolation, schema-less metafields). The debt is concentrated in three areas: (1) `core/` reaching into plugin models (violating the contract it documents), (2) test coverage gaps on critical paths, and (3) CI/CD gaps that mean "green build" ≠ "safe to ship." None of the issues require a rewrite — all are surgical fixes that can land in 1-2 PRs each.

**This document is observation-only; no code was changed.**
