---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/analytics/services_cohorts.py

Symbols in `plugins/installed/analytics/services_cohorts.py`.

- L51 `CohortCell` (class) — One (cohort_week, period_n) intersection.
- L62 `CohortRow` (class) — One cohort across its periods.
- L71 `compute_cohorts(*, cohort_count: int=DEFAULT_COHORT_COUNT, period_count: int=DEFAULT_PERIOD_COUNT, metric: str='order')` (function) — Return cohort table data for the dashboard.
- L166 `_monday(d: date)` (function) — Return the Monday of the ISO week containing d.
- L171 `_cohort_users_by_week(User, earliest: date, latest: date)` (function) — Map week-start → set of user PKs created that week.
- L188 `_count_users_with_order(user_ids: list[int], start: date, end: date)` (function) — Count distinct user_ids who placed at least one order in [start, end).
- L206 `_count_users_with_event(user_ids: list[int], start: date, end: date)` (function) — Count distinct user_ids with any analytics event in [start, end).
- L224 `_sum_revenue(user_ids: list[int], start: date, end: date)` (function) — Sum order totals for the cohort in this period.
- L244 `step_dropoffs(*, steps: list[str], days: int=30)` (function) — For each consecutive step pair, return drop-off rate.
- L281 `period_comparison(*, days: int=30)` (function) — Compare orders + revenue this `days`-day period to the prior
