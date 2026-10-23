---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/self_improvement/tests/test_error_log_watermark.py

Symbols in `core/self_improvement/tests/test_error_log_watermark.py`.

- L28 `ErrorLogWatermarkExecuteTests` (class)
- L29 `test_execute_does_not_collapse_watermark_to_now(self)` (method) — An error 30 min old, with a prior COMPLETED run 1h ago, must still be
- L67 `test_execute_opens_its_own_job_but_ignores_it_for_watermark(self)` (method) — Sanity check on the mechanism: execute() writes an ingest job for this
- L95 `LastSuccessfulRunTests` (class)
- L96 `test_ignores_unfinished_job_uses_finished_one(self)` (method) — `_last_successful_run()` must derive the watermark from the most recent
