---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/experiments/tests/test_assignment.py

Symbols in `plugins/installed/experiments/tests/test_assignment.py`.

- L32 `_AnonymousUser` (class)
- L37 `_AuthUser` (class)
- L40 `__init__(self, pk)` (method)
- L44 `_request(visitor_cookie='', user=None)` (function)
- L53 `DeterminismTests` (class)
- L54 `setUp(self)` (method)
- L66 `test_same_visitor_always_same_variant(self)` (method)
- L74 `test_different_visitors_can_get_different_variants(self)` (method)
- L82 `test_unknown_experiment_returns_control(self)` (method)
- L86 `test_paused_experiment_returns_control(self)` (method)
- L98 `WeightDistributionTests` (class)
- L99 `test_70_30_distribution_approximate(self)` (method)
- L122 `AssignmentPersistenceTests` (class)
- L123 `setUp(self)` (method)
- L135 `test_first_call_writes_assignment_row(self)` (method)
- L143 `test_repeat_calls_do_not_duplicate(self)` (method)
- L152 `test_exposure_increments(self)` (method)
- L160 `ConversionAttributionTests` (class)
- L161 `setUp(self)` (method)
- L173 `test_conversion_attributed_to_assigned_variant(self)` (method)
- L190 `test_no_assignment_no_conversion(self)` (method)
- L200 `ResultsLiftMathTests` (class)
- L201 `setUp(self)` (method)
- L213 `_seed(self, *, variant, exposures, conversions)` (method)
- L224 `test_no_data_does_not_crash(self)` (method)
- L232 `test_lift_pct_correct(self)` (method)
- L243 `test_small_sample_no_significance(self)` (method)
- L252 `VisitorIdResolutionTests` (class)
- L253 `test_authenticated_user_uses_user_pk(self)` (method)
- L259 `test_anonymous_user_with_cookie(self)` (method)
- L265 `test_anonymous_user_no_cookie_mints_one(self)` (method)
