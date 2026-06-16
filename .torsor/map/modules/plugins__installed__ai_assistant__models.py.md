---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/models.py

Symbols in `plugins/installed/ai_assistant/models.py`.

- L9 `AgentIntent` (class) — Lifecycle record for a single agent action against the platform.
- L122 `__str__(self)` (method)
- L126 `AgentIntentEvent` (class) — Immutable audit log of every state transition on an AgentIntent.
- L158 `AgentMemory` (class)
- L203 `AgentRegistration` (class)
- L238 `save(self, *args, **kwargs)` (method)
- L245 `remaining_budget(self)` (method) — Decimal remaining budget, or None when no cap is configured.
- L251 `can_afford(self, amount)` (method) — Return True iff the configured budget can absorb `amount`.
- L260 `PromptTemplate` (class)
- L293 `AIExperiment` (class)
- L332 `AIInteraction` (class)
- L378 `DemandForecast` (class)
- L395 `MerchantInsight` (class)
- L431 `ProductEmbedding` (class) — Vector embedding for a product's description + key attributes.
- L457 `DynamicPriceRule` (class)
