---
type: active-context
status: active
tags:
- active
links: []
created: '2026-06-13T00:48:59'
updated: '2026-06-13T00:48:59'
---

# Active Context

## Current focus
Stabilizing dotbooks.store after two concurrent-session prod outages, then shipping small merchant features. Currently between tasks — main is clean and prod is healthy (86 plugins, 200).

## Open questions
Roadmap-plugin quality debt: ~20 PR#62 plugins boot but have zero tests and overlap existing systems (the `journal` plugin duplicates the CMS journal; `ai_stylist` 'Aria' chat floats site-wide via global_below_body — user noticed it). Should these stubs get a quality pass, be consolidated/removed, or stay? Branch protection on main still does NOT require CI to pass (both 503s merged despite gates) — needs a GitHub Settings/gh change to enforce. Housekeeping left: parked stash@{0} (non-mine WIP), stray untracked files (_test_settings_tmp.py, dash-*.png, design/, uv.lock — uv.lock probably should be committed). A concurrent Claude session is actively merging PRs to main (dashboard IA redesign #66-69), so expect frequent rebases.
