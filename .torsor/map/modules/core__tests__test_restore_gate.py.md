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

# core/tests/test_restore_gate.py

Symbols in `core/tests/test_restore_gate.py`.

- L17 `_StateFolder` (class)
- L18 `setUp(self)` (method)
- L26 `_running(self, age=0.0, info=None)` (method)
- L35 `GateTests` (class)
- L36 `test_every_page_says_restoring_while_a_restore_runs(self)` (method)
- L45 `test_the_liveness_probe_stays_open(self)` (method)
- L50 `test_no_restore_no_gate(self)` (method)
- L53 `test_a_restore_that_stopped_beating_no_longer_closes_the_store(self)` (method)
- L58 `GatePlacementTests` (class)
- L59 `test_the_gate_runs_before_anything_reads_the_database(self)` (method)
- L65 `test_reused_connections_are_checked_first(self)` (method)
- L71 `LockTests` (class)
- L72 `test_a_second_restore_is_refused_while_one_runs(self)` (method)
- L78 `test_a_dead_restore_is_taken_over(self)` (method)
- L84 `test_finish_records_the_outcome_and_opens_the_store(self)` (method)
- L90 `test_stalled_names_the_restore_that_stopped(self)` (method)
- L95 `test_nothing_stalled_while_a_restore_beats(self)` (method)
- L99 `test_nothing_before_the_first_restore(self)` (method)
- L104 `test_the_heartbeat_keeps_the_restore_alive(self)` (method)
