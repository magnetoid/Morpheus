---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-02T03:23:05'
updated: '2026-07-02T03:23:05'
rules:
- id: error-capture-is-core-not-plugin
  pattern: record_error|ErrorEvent|task_failure|capture_exception
  message: "Error CAPTURE/STORAGE lives in core/errors/ (un-disable-able immune-system\
    \ infra). Record via core.errors.services.record_error \u2014 never define a second\
    \ ErrorEvent model or import a plugin's recorder from core/project code (core->plugin\
    \ boundary). A plugin may only contribute the optional error DASHBOARD surface\
    \ over core/errors. (ADR: error logging is core.)"
---

# ADR 0025: Error logging is a CORE system (core/errors); the observability plugin is an optional surface over it, not a parallel store

## Context
Error/exception logging is currently split across two layers with two parallel ErrorEvent tables (an ADR-0006/PR-#62 'one concept, two owners' violation): (1) core/errors/ owns a RICH ErrorEvent (fingerprint dedup, kind/level, exception_class, traceback, request_id, user FK, ip_hash, path/method/status, indexed) written by web middleware, the hooks bus, and consumed by the self-improvement loop (core/self_improvement/collectors/error_log.py); (2) plugins/installed/observability/ owns a SIMPLER, parallel ErrorEvent (source, message, stack_trace, channel) written by morph/celery.py's task_failure handler. Consequences: Celery task failures land in a different table than web errors — invisible to the core error dashboard, the fingerprint dedup, and the self-improvement engine; and morph/celery.py importing plugins.installed.observability.services.record_error is a wrong-direction (core/project -> plugin) coupling. The user asked whether error logging should be an app or a core system.

## Decision
Error CAPTURE + STORAGE + the single record_error() API are a CORE system (core/errors/): the ErrorEvent model, middleware/hook/Celery capture, fingerprint dedup, request_id correlation, and retention/prune. Rationale: (a) you need error logging most exactly when something is broken, so it must be un-disable-able — a togglable plugin logger blinds you when it matters; (b) core code (middleware, Celery, hooks) and the self-improvement loop must record/read errors without importing a plugin (the core->plugin boundary forbids it; celery.py already violates it); (c) the self-improvement loop is core and 'cannot be a togglable plugin', and it consumes errors; (d) the compass lists 'observability' among core foundations. A plugin owns ONLY the optional PRESENTATION/analytics surface over core/errors — dashboard views, charts, GraphQL, rollups, and Sentry/OTel export — contributed so that disabling it hides the dashboard but never stops capture. The observability plugin keeps its legitimate MerchantMetric (channel-scoped business analytics) but must NOT own a second ErrorEvent; its record_error becomes a thin adapter into core/errors (or is removed), and morph/celery.py records via core.errors instead of the plugin.

## Consequences
Consolidation work: (1) route morph/celery.py task_failure through core.errors.services.record_error (fixes the boundary violation + unifies Celery errors into the fingerprinted core table); (2) make the observability plugin's error dashboard/GraphQL read core/errors.ErrorEvent; (3) migrate/retire the plugin's parallel ErrorEvent table (data migration to fold existing rows into core, then RemoveField/RemoveModel). Do it non-destructively first (unify capture, keep old table read-only) before the destructive migration. Enterprise-readiness Phase 2 (observability). Guarded by the core-boundary check once the celery import is removed.
