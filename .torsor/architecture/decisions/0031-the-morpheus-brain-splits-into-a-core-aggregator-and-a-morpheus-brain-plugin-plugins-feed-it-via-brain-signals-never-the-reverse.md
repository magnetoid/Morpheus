---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-06T21:36:49'
updated: '2026-07-06T21:36:49'
rules:
- id: morpheus-brain-core-vs-plugin-split
  severity: error
  text: "core/brain/ (signals aggregator, analyst, log handler, beat tasks) is permanent\
    \ kernel and must NEVER import plugins.installed.* \u2014 plugin-owned Brain data\
    \ (SEO/catalog/insights/DailyReport slices) is contributed ONLY through the BRAIN_SIGNALS\
    \ filter via a plugin's register_hook(events.BRAIN_SIGNALS, ...) subscriber. A\
    \ new core\u2192plugin import in core/brain/, or moving the core aggregator into\
    \ the morpheus_brain plugin, is forbidden. The morpheus_brain plugin owns DailyReport\
    \ + the /dashboard/brain/ surface only; it renders the core engine, it does not\
    \ host it."
---

# ADR 0031: The Morpheus Brain splits into a core aggregator and a morpheus_brain plugin; plugins feed it via BRAIN_SIGNALS, never the reverse

## Context
The Morpheus Brain is a read-only intelligence console. Its parts live on both sides of the core/plugin line and this was being conflated: `core/brain/` (signals gathering, the AI analyst, log handler, beat tasks — non-disableable kernel) vs the `morpheus_brain` plugin (the DailyReport model + the /dashboard/brain/ surface page). Until the arch-debt refactor (Phase 8a, 2026-07-06), `core/brain/signals.py` hard-imported four plugins' models (seo, catalog, ai_assistant, morpheus_brain) to assemble its snapshot — a wrong-direction core→plugins.installed.* coupling (6 rows on the core-boundary ratchet) and a disable-safety leak (a disabled plugin's Brain panel still rendered because the import was only try/except-guarded, which guards absence, not disable). This is the same class as ADR 0023 and the ADR 0017 kernel-purity principle.

## Decision
Keep the split explicit and permanent. (1) The Brain ENGINE stays core: `core/brain/` owns signal aggregation (`gather_all`/`_gather_all_uncached`), the AI analyst, the error-log handler, and the beat tasks — it is part of the self-improvement immune system and cannot be a togglable plugin. (2) `core/brain/signals.py` seeds only the core-owned sections (plugin health, error-log + code-quality signals, the setup checklist) and fires the `BRAIN_SIGNALS` filter (core/hooks.py MorpheusEvents.BRAIN_SIGNALS). (3) Every plugin-owned slice is CONTRIBUTED by its plugin through a `register_hook(events.BRAIN_SIGNALS, self.on_brain_signals)` subscriber that merges its own disjoint keys into the value dict: seo → content.{low_seo,seo_avg,seo_low_count,seo_total,notfound} + storefront.{cwv,seo_flags}; catalog → content.catalog; ai_assistant → improvements.insights; morpheus_brain → reports. (4) The kernel imports NO plugin model; a disabled contributor's slice vanishes for free (the hook bus skips inactive owners), so its Brain panel disappears. (5) The `morpheus_brain` plugin owns only its own data (DailyReport) and its surface page — it renders the core engine, it does not host it. Data that a plugin owns (like DailyReport) is surfaced to the core aggregator only via BRAIN_SIGNALS, never by core importing the plugin. Any new Brain data source is a new BRAIN_SIGNALS subscriber in the owning plugin — never a new import in core/brain/.

## Consequences
Core-boundary ratchet dropped 18→12 (6 brain rows cleared, same commit). Brain aggregator output is behaviour-preserving with all plugins active (golden test) and each panel is now disable-safe (per-contributor deactivate test) — plugins/installed/morpheus_brain/tests/test_brain_signals_filter.py. The private seo.views._cwv_summary was promoted to a public seo.services.cwv_summary() as part of this (it was the most fragile leak — silently swallowed under suppress). Reports section: core seeds reports={'available': False}; morpheus_brain flips it True on publish, so a disabled morpheus_brain shows 'Reports service unavailable' rather than a phantom empty panel. Trade-off: the snapshot dict shape is now assembled across five files (core seed + four subscribers) instead of one — mitigated by the disjoint-keys invariant (order-independent merges) and the golden test.
