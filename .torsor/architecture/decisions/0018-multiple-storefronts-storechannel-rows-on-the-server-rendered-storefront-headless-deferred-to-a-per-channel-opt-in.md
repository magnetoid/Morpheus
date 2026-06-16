---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-14T19:56:11'
updated: '2026-06-14T19:56:11'
rules:
- id: storefront-server-rendered-not-headless
  pattern: ^(frontend|spa|headless|next-storefront|nuxt-storefront)/
  message: "Multiple storefronts = StoreChannel rows + theme-per-channel on the EXISTING\
    \ server-rendered Django storefront, NOT a decoupled JS frontend tree. Headless\
    \ was deliberately deferred (docs/plans/multi-storefront.md, ADR): a JS frontend\
    \ strands the ~46 plugins that render via {% storefront_blocks %}. Headless is\
    \ a later, per-channel opt-in over the existing GraphQL API \u2014 not a parallel\
    \ frontend."
- id: one-storefront-app-n-channels
  pattern: plugins/installed/storefront[0-9_]
  message: A second storefront is a StoreChannel ROW, not a second storefront plugin.
    One storefront app renders N channels; per-storefront difference is channel-scoped
    data + theme-per-channel (override keyed by channel FK), never a forked/cloned
    storefront plugin or a parallel table.
---

# ADR 0018: Multiple storefronts = StoreChannel rows on the server-rendered storefront; headless deferred to a per-channel opt-in

## Context
The user wants one Morpheus backend with one shared product database serving several storefronts (different domains, languages, curation, branding, SEO and analytics), with dashboard control over what is shared vs. per-storefront, and per-storefront performance reporting. The instinct was to go "headless" to get this. Research found the two are orthogonal: multi-storefront is a data+routing concern; headless is a presentation-delivery concern. Crucially the multi-tenant spine already exists in core/models.py — StoreChannel (domain-routed via resolve_for_request) + ProductChannelListing (per-channel price/visibility over a single shared catalog.Product). Going headless would strand the ~46 plugins that render storefront surfaces server-side via {% storefront_blocks %} and is not required for multiple storefronts. Full plan: docs/plans/multi-storefront.md.

## Decision
Deliver multiple storefronts on the EXISTING server-rendered Django storefront by finishing the StoreChannel spine, NOT by going headless. A storefront IS a StoreChannel row. Host->storefront resolution has a single source of truth: StoreChannel.resolve_for_request(request) — no view/plugin/middleware hand-parses the Host header. Per-storefront difference is an OVERRIDE keyed by a channel FK (theme-per-channel, ProductChannelListing for price/visibility, a channel FK on seo overrides, a channel dimension on analytics) — shared by default, override only where it differs, one concept = one owner, never a parallel/forked table or a second storefront plugin. Headless is explicitly DEFERRED to a later, per-channel opt-in over the already-mature GraphQL API: any one storefront can go headless without forcing the others, and only then. Per-channel order/customer tenancy and per-channel inventory pools are out of scope until a concrete need.

## Consequences
Multi-storefront ships as incremental, independently-deployable phases on existing bones (Phase 1 channel resolution + theme-per-channel; then seo, analytics, per-product sharing UI) rather than a months-long rewrite. The plugin ecosystem keeps working per-storefront because rendering stays server-side. Channels remain a core capability (core/models.py); per-channel surfaces stay plugin-contributed and disable-safe. Reviewers should reject (a) a decoupled JS frontend tree introduced under the banner of "multiple storefronts", (b) a forked/cloned storefront plugin per storefront, and (c) any host-header parsing that bypasses resolve_for_request. Headless remains available later as a per-channel delivery mode, judged on its own merits, not bundled into this work.
