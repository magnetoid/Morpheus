---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-07T15:28:09'
updated: '2026-06-07T15:28:09'
rules:
- id: core-owns-interfaces-not-engines
  pattern: core/.*(tax|payment|gateway|shipping_rate|discount_engine)
  message: Tax/payment/shipping/discount ENGINES are plugins behind a core hook/interface.
    Core only defines + calls the interface; the implementation lives in plugins/installed/<name>/.
- id: feature-code-not-in-core
  pattern: core/.*(models|views)\.py
  message: Is this kernel/spine, or a feature? Non-spine features belong in a plugin,
    not core/. Core should own extension points, not feature logic.
---

# ADR 0010: Tiny commerce core: spine + kernel + extension points; everything else is a plugin

## Context
As the platform grew to ~65 plugins, the question is what is permanently "core" vs pluggable. Naively, taxes/payments feel core, but hardcoding them into checkout would block alternative engines and bloat the core. The risk is feature code accreting in core/ over time, making the platform rigid and un-seamless.

## Decision
Keep the core tiny and its job is to OWN EXTENSION POINTS, not features. Core = the commerce spine (catalog → cart → checkout → fulfillment) + the kernel (auth, hooks bus, settings, request lifecycle, i18n, observability, the self-improvement loop, the safety boundary). Tax engines, payment gateways, and every non-spine capability are PLUGINS behind a core interface/hook: checkout calls a tax hook and a payment hook; the engines plug in. When deciding core-vs-plugin: if it isn't required for catalog→cart→checkout→fulfillment or the kernel, it's a plugin. The core exposes named extension points (settings categories, dashboard sections, storefront slots, the account_nav slot, the agent tool registry, core.hooks) and plugins contribute INTO them.

## Consequences
The platform stays flexible (swap tax/payment engines without touching checkout) and coherent as plugins multiply. New "core" code must be kernel/spine or an extension-point; feature logic in core/ is a smell. Reinforces the existing CLAUDE.md architectural compass.
