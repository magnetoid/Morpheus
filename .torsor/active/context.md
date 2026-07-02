---
type: active-context
status: active
tags:
- active
links: []
created: '2026-07-01T04:29:08'
updated: '2026-07-01T04:29:08'
---

# Active Context

## Current focus
Plugin disable-safety (ADR 0023/0024) shipped. Localization Phases 2-4 and the bookvault migration remain as the next threads.

## Open questions
1) bookvault still hard-imports into admin_dashboard/views_split/products.py (product-list column L90 + fulfilment card L397) — self-hides on is_authenticated() so it only leaks if disabled-while-configured. Migrate: fulfilment card -> PRODUCT_FORM_CARDS; list column -> needs a NEW PRODUCT_LIST_COLUMNS hook. Logged in ADR 0024 + CLAUDE.md.
2) Localization Phase 1b leftover: per-language hreflang alternates. Phases 2-4: gettext UI + AI .po autofill; content editor; emails/dashboard/RTL (docs/plans/full-localization-2026-06.md).
3) Foundational-plugin imports (orders in storefront/account.py) are exempt from the disable test (never disabled) — documented, no action.
4) 6 untracked ssh_test*.py files in working tree (pre-existing, not mine) — offered cleanup, awaiting user.
