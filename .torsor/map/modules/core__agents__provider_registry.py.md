---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/agents/provider_registry.py

Symbols in `core/agents/provider_registry.py`.

- L30 `ProviderConfig` (class)
- L99 `_default_active_provider_name()` (function) — Active provider from Django settings only (no plugin/dashboard).
- L104 `_default_get_provider_config(provider: str | None=None)` (function) — Env/settings-only resolver. Never raises — empty strings when unset.
- L127 `_ProviderConfigRegistry` (class) — Holds the active resolver. Plugins register a richer one; core falls
- L132 `__init__(self)` (method)
- L136 `register(self, config_resolver: Callable[[str | None], ProviderConfig], active_resolver: Callable[[], str] | None=None)` (method) — Install a resolver (idempotent — last registration wins).
- L146 `reset(self)` (method) — Drop any registered resolver (used by tests + on plugin disable).
- L151 `get_provider_config(self, provider: str | None=None)` (method)
- L161 `get_active_provider_name(self)` (method)
- L175 `get_provider_config(provider: str | None=None)` (function) — Resolve config for a provider (or the active one). Never raises.
- L180 `get_active_provider_name()` (function) — The active provider name (dashboard-aware when the plugin is loaded).
