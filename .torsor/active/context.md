---
type: active-context
status: active
tags:
- active
links: []
created: '2026-07-01T03:03:29'
updated: '2026-07-01T03:03:29'
---

# Active Context

## Current focus
Localization/i18n storefront rollout (Phase 1 done through 1b; Phases 2-4 pending). Side-stream this session: Linda per-page helper UX (shipped) + hardening Torsor drift guards (ADR 0023 added, ADRs 0006/0021 formalized).

## Open questions
1) Push b8fc602 (ADR rule guards, docs-only) with the next code push to avoid a standalone Coolify rebuild.
2) Remaining Phase 1b piece: per-language hreflang alternates (extend seo/templatetags/seo.py:seo_hreflang, currently per-market).
3) Phase 2: gettext UI-string translation + AI .po autofill. Phase 3: content-translation editor + AI autofill. Phase 4: emails/dashboard UI/formatting/RTL (spec: docs/plans/full-localization-2026-06.md).
4) Disable-test debt (ADR 0023): storefront account sub-pages (orders list, credits, downloads) still query plugin models directly — not yet disable-safe.
