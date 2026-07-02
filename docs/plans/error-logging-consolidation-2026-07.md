# Error-logging consolidation — one core system (ADR 0025)

**Decision (ADR 0025):** error *capture + storage + `record_error`* is a **core** system
(`core/errors/`); a plugin may own only the optional dashboard/analytics *surface* over it.

## Problem (confirmed)
Two parallel `ErrorEvent` tables — an ADR-0006 "one concept, two owners" violation:
- **`core/errors/ErrorEvent`** — rich: fingerprint dedup, kind/level, exception_class,
  traceback, request_id, user FK, ip_hash, path/method/status, indexed. Written by web
  middleware + hooks; **consumed by the self-improvement loop**.
- **`observability/ErrorEvent`** (plugin) — simple: source, message, stack_trace, channel.

`record_error` (the plugin's string-based version) has **4 callers, 2 of which cross the
core→plugin boundary the wrong way**:

| Caller | Has exception? | Boundary violation? |
|---|---|---|
| `morph/celery.py` (task_failure) | yes (`exception`) | yes (project→plugin) |
| `core/brain/log_handler.py` | sometimes (`record.exc_info`) | **yes (core→plugin)** |
| `api/exception_handler.py` | yes (`exc` + request) | project→plugin |
| `api/schema.py` (GraphQL) | yes (`original`) | project→plugin |

Result: Celery/API/GraphQL/brain errors land in the plugin table — **invisible to the
core error dashboard, fingerprint dedup, and the self-improvement engine** — while web
errors land in core. Errors are split by source.

## Target
`core/errors/services.py` is the single capture API:
- `record_error(exc, *, request=None, kind='server', level='error', extra=None)` — exists.
- **New** `record_message(message, *, level='error', kind='server', source='', stack_trace='', extra=None, request=None)`
  — for callers that have only a formatted string/log record (brain log_handler without
  `exc_info`). Fingerprint from (source|kind + message head). Same scrub/truncate as `record_error`.

The `observability` plugin keeps `MerchantMetric` (legit channel analytics) and its
dashboard, but reads **`core/errors.ErrorEvent`**; its own `ErrorEvent` + `record_error`
are retired.

## Plan (incremental, non-destructive first)

### Phase A — unify capture (safe, no data loss)
1. Add `core/errors/services.record_message(...)`.
2. Repoint the 4 callers to core:
   - celery → `record_error(exception, kind='server', extra={source:'celery', task, task_id})`
   - api/exception_handler → `record_error(exc, request=context['request'], extra={source:'api'})`
   - api/schema → `record_error(original, extra={source:'api.graphql', request_id, type})`
   - brain/log_handler → `record_error(exc)` when `exc_info` else `record_message(msg, source='brain')`
3. Make `observability.services.record_error` a **forwarding shim** to core (back-compat for
   any missed caller; stops new writes to the plugin table).
4. Verify: `scripts/check_core_boundary.py` (the 2 core→plugin violations disappear),
   py_compile, ruff, error tests.

### Phase B — dashboard over core
5. Point the observability plugin's error views/GraphQL at `core/errors.ErrorEvent`
   (or move the error dashboard into `core/errors/` and leave the plugin as metrics-only).

### Phase C — retire the parallel table (destructive — needs explicit go)
6. Data migration: fold existing `observability.ErrorEvent` rows into `core/errors.ErrorEvent`
   (map source→metadata, stack_trace→traceback, synth fingerprint), then `RemoveModel`.
   Follows the Postgres-safe pattern; sqlite green ≠ safe (CI migrations job on Postgres is the gate).

## Enhancements (fold in with Phase A/B)
- **Consistent context**: ensure request_id + user captured on API/GraphQL errors (they weren't).
- **Silent-except audit** (audit risk: ~700 bare `except`): a follow-up pass to route the
  ones that swallow real errors through `record_error`/`record_message` instead of `pass`.
- **Rate-limit/dedup notifications** off the existing fingerprint so an error storm doesn't
  flood the dashboard/alerts.

## Verification
- `check_core_boundary.py` shrinks (2 violations removed).
- Error-capture tests: a task failure, a DRF exception, a GraphQL resolver error, and a
  brain log record all produce exactly one `core/errors.ErrorEvent` with the right kind/source.
- Prod smoke: trigger a handled 500 and confirm it appears in the core error dashboard.
