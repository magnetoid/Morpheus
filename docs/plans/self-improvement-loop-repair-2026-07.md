# Self-improvement loop repair (core-audit C2/C4) — 2026-07-19

**Ship together** (coupling landmine): reviving collectors (bugs 2, 3) while the
heal-loop floods (bug 1) amplifies the flood. All four land in one deploy.

## Bug 1 — heal-loop infinite re-run (terminal state)
`heal.execute_queue()` selects `status__in=('approved','auto_applied')`; on
success `run_one` writes `status='auto_applied' if rec.status=='auto_applied'
else 'merged'` (`heal.py:138`) → an auto row lands back in the selection set and
re-runs every 5 min forever. Root cause: `auto_applied` overloaded as both
"queued for autonomous run" AND "successfully run".
- `models.py`: add `('applied','Applied')` terminal status.
- `heal.py:138`: `status='applied' if rec.status=='auto_applied' else 'merged'`.
- `admin_dashboard/views_split/self_improvement.py:44`: KPI `auto_applied_7d` →
  `status='applied'`.
- `tasks.py:88` digest `accepted`: add `'applied'` to the status set.

## Bug 2 — zero_search never fires (kwarg + wrong site)
`catalog.py:983` fires `results_count=None` BEFORE the search runs, from
`/search/` (mood/semantic landing). Handler `on_search_performed` reads
`result_count` (name mismatch) and needs `==0`. Header search posts to
`/products/` (`base.html:719`) which fires NOTHING. Analytics reads only
`query`+`request` (never the count) so renaming/moving is safe.
- `product_list` (`catalog.py`, after `Paginator(qs,60)` ~line 211): when `q`,
  fire `SEARCH_PERFORMED(query=q, result_count=paginator.count, request=...)`.
- `search()` (`catalog.py:976-987`): drop the count-less unconditional fire.
  Keyword branch redirects to `/products/` (fires there — no double). Semantic
  branch: fire with `result_count=len(products)` after `data` computed.
- zero_search handler already reads `result_count` — no change.

## Bug 3 — error_log reads the retired model
`error_log.py` reads `observability.ErrorEvent` (nothing writes it since ADR
0025); live model is `core.errors.ErrorEvent`. Field remap:
`occurred_at→created_at`, `source→kind`, `stack_trace→traceback`, native
`exception_class`/`fingerprint` available. Update `_error_event_model`,
`run()`, `_signal_from`, `_severity_for`, docstring. `settings.py` comment.

## Bug 4a — suppression never matches (vocab)
Reject/snooze write `match_class=rec.class_name` + `match_fingerprint=str(signal
PK)`; `emit_signal` filters `match_class=source` + `match_fingerprint=<hash>`.
Both axes mismatch → reject never sticks.
- `self_improvement.py` reject()/snooze(): load evidence `SiSignal` rows, write
  one suppression per `(sig.source, sig.fingerprint)`.
- `services.py emit_signal`: honor class-wide (blank fingerprint) too:
  `Q(match_fingerprint=fingerprint) | Q(match_fingerprint='')`.

## Bug 4b — recommendation dedup missing
`_process_cluster` always `create()`s → same issue re-proposed nightly.
- `models.py` SiRecommendation: add `fingerprint` CharField(128, blank, indexed).
- `recommend.py`: `rec_fp = fingerprint_for(class_name, cluster.fingerprint)`;
  skip if active rec (`status in proposed/approved/auto_applied/in_pr`) with that
  fp exists; set on create.

## Migration
One SiRecommendation migration: `applied` choice + `fingerprint` field (additive,
safe on Postgres + sqlite).

## Tests (DATABASE_URL='sqlite:///:memory:')
- heal: auto_applied success → `applied`, not re-selected next pass.
- zero_search: product_list with 0-match q emits signal; >0 doesn't.
- error_log: reads core.errors.ErrorEvent, maps fields.
- suppression: reject writes (source,fp); emit_signal drops it; class-wide.
- dedup: analyzer skips duplicate fp; distinct fp still creates.

Run: `plugins.installed.storefront plugins.installed.analytics
plugins.installed.admin_dashboard` + `core.self_improvement`.
