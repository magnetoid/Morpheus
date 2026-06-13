---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-13T18:47:49'
updated: '2026-06-13T18:47:49'
rules:
- id: core-owns-interfaces-not-engines
  pattern: core/.*(tax|payment|gateway|shipping_rate|discount_engine)
  message: "Tax/payment/shipping/discount ENGINES are pluggable plugins behind a core\
    \ hook/interface \u2014 even when the platform's commerce is advanced. Core defines\
    \ + calls the interface; the (possibly very powerful) implementation lives in\
    \ plugins/installed/<name>/."
- id: feature-code-not-in-core
  pattern: core/.*(models|views)\.py
  message: "Kernel/spine, or a feature? Build features as deep as you like \u2014\
    \ but feature logic belongs in a plugin, not core/. Core owns extension points;\
    \ 'advanced & powerful' lands as well-factored plugins, never as feature code\
    \ in core/."
supersedes: 0010-tiny-commerce-core-spine-kernel-extension-points-everything-else-is-a-plugin
---

# ADR 0017: Advanced, powerful commerce core — delivered through modularity (supersedes "tiny core")

## Context
ADR 0010 framed the commerce core as "tiny: spine + kernel + extension points." In practice the word "tiny/minimal" reads as a cap on ambition and was even cited to argue against legitimately ambitious improvements. The goal is the opposite: Morpheus should be an ADVANCED, POWERFUL e-commerce platform — deep catalog (variants, bundles, digital, subscriptions), rich pricing/promotions, multi-currency/markets, B2B, inventory, checkout and fulfillment — a serious commerce engine, not a toy spine. The hard constraint is that this power must NOT come from a monolith: the modularity contract (disable a plugin → its surface vanishes), the pluggable-engines design, the agent tool registry, and the self-improvement loop all depend on a clean kernel. So the reframe must raise ambition while keeping modularity as the delivery mechanism, not remove it.

## Decision
Build an advanced, powerful commerce platform — and deliver that power THROUGH modularity, not despite it. "Powerful" means deep, capable commerce features and a first-class agent/dashboard/storefront surface; it does NOT mean feature code accreting in core/. The kernel stays a focused set of clean extension points (core.hooks, settings categories, dashboard sections, storefront slots, account_nav, the agent tool registry) — that is the MECHANISM that lets the powerful platform stay flexible and agent-actionable, not a limit on how capable the platform may be. Foundational commerce (catalog, cart, checkout, pricing, inventory, orders, fulfillment, payments, tax, shipping) ships as required plugins behind core interfaces; advanced capabilities are built deep but still CONTRIBUTED into named surfaces, never hardcoded. Tax/payment/shipping/discount remain pluggable engines behind core hooks. When choosing core-vs-plugin: the kernel owns extension points; everything with feature logic — however advanced — is a well-factored plugin. Be ambitious about depth; be disciplined about where it lands.

## Consequences
Ambition is explicit: no apologising for depth, no "keep it minimal for its own sake." Advanced features are encouraged — but they land as plugins/extension-point contributions, so the platform stays swap-able (any engine), disable-safe (the modularity contract), and agent-legible. Audit/architecture recommendations are no longer to be rejected merely for "expanding scope"; they're judged on whether they keep the kernel clean and the surfaces modular. A monolithic core, or feature engines hardcoded into checkout, remain smells. Supersedes ADR 0010; its two drift-guard rules carry forward with the ambition reframing.
