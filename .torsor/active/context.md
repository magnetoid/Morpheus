---
type: active-context
status: active
tags:
- active
links: []
created: '2026-06-04T03:31:31'
updated: '2026-06-04T03:31:31'
---

# Active Context

## Current focus
Goal "improve Linda (assistant) + central updating system" — core delivered + shipped. A1: /dashboard/updates/ now triggers the guarded self-updater (check + apply, opt-in MORPHEUS_SELF_UPDATE_ENABLED). B: Linda gained 4 gated platform-ops tools (updates.status, updates.apply hard-gated, settings.set, plugins.toggle refusing protected) → 42 tools, persona updated; inventory/SEO/CRM stay Worker-delegated. Plan + analysis: docs/plans/linda-and-central-updating-2026-06.md.

## Open questions
Linda/updating remaining breadth (future, fresh session): direct shop-control tools (theme switch, workflow trigger, refunds, webhook mgmt); updating Phase 5 (per-plugin/theme update channels, AI-assisted propose/stage, maintenance-mode middleware, DB-snapshot restore). 'is_plugin_protected' is core/safety.py. Linda tool pattern: core/assistant/tools/*.py @tool + register in tools/__init__.get_default_tools; Tool.invoke RE-RAISES ToolError (tests use assertRaises). Also still open from earlier: PAYMENTS settings de-dup; retire book.* metafields once author_detail/PLP filters move to model; pre-existing cloudflare test_purge failures.
