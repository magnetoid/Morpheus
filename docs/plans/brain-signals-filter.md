# Follow-up: BRAIN_SIGNALS contribution filter (deferred from v0.2.5)

`core/brain/signals.py` imports `plugins.installed.*` (seo.models, seo.views._cwv_summary,
catalog.models, ai_assistant.models) — a CLAUDE.md "core never imports plugins.installed.*"
violation (guarded by `suppress`, so it degrades rather than crashes, but it's debt).

**Decision (workflow-verified):** fix it as its OWN focused PR, not bundled with the
error-pipeline / caching hardening. Mechanically a clean ~5-file change:

1. Declare `MorpheusEvents.BRAIN_SIGNALS = 'brain.signals'` in `core/hooks.py` (filter).
2. Each owning plugin registers a handler in `ready()` and folds its data into `value`:
   - `seo` → low SEO audits, avg, 404s, CWV (`_cwv_summary`), discovery flags.
   - `catalog` → content gaps (active count, missing-description count).
   - `ai_assistant` → unread MerchantInsights. **Contract must emit 4 keys**
     (title, type, priority, impact) — the verifier caught a 3-key version that would
     silently drop `impact` from the digest.
3. `core/brain/signals.py` fires `hook_registry.filter(BRAIN_SIGNALS, value={...})` instead
   of importing plugins. KEEP the plugin-registry + self_improvement (`SiSignal`/
   `SiRecommendation`) reads — those are core-legal.

Keep the 90s `gather_all()` cache wrapping the filter call.
