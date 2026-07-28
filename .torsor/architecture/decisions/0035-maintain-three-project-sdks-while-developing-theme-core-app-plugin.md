---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-28T00:54:58'
updated: '2026-07-28T00:54:58'
rules: []
---

# ADR 0035: Maintain three project SDKs while developing: Theme, Core app, Plugin

## Context
The project's public extension surface today is a single `morpheus/` package — a plugin-authoring facade (exports Plugin, DashboardPage, SettingsPanel, StorefrontBlock, EmailTemplateDef, events; plus hooks/models/events/forms/views). The user wants the SDK rebuilt and separated into three distinct SDKs — a Theme SDK, a Core-app SDK, and a Plugin SDK — and this adopted as a standing development practice.

## Decision
Rebuild the project SDK as THREE separated SDKs: (1) Theme SDK — building storefront themes (slots, StorefrontBlock rendering, template tags, theme manifest); (2) Core-app SDK — the core kernel API (hooks/filters bus, agents runtime + tools, settings, audit, safety boundary, i18n); (3) Plugin SDK — the plugin authoring contract (Plugin base, plugin.py manifest, contribution dataclasses, migrations/tests scaffolding). STANDING RULE: while developing any feature, build/extend and keep current the relevant one of these three SDKs in the same change — theme work updates the Theme SDK, core-kernel work updates the Core-app SDK, plugin-contract work updates the Plugin SDK. New extension points ship as first-class SDK entries with docs, not ad-hoc imports.

## Consequences
Every change that touches a theme, core-kernel, or plugin-contract surface must surface/update the corresponding SDK in the same commit (mirrors the existing 'code and docs ship together' rule). The three SDKs become the enforced public boundaries; ad-hoc cross-layer imports are discouraged in favour of the SDK a layer is meant to consume. Requires an up-front SDK-restructure effort to carve `morpheus/` into the three namespaces without breaking the ~60 plugins that import from it (back-compat re-exports during migration).
