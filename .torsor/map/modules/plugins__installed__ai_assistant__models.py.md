---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/ai_assistant/models.py

Symbols in `plugins/installed/ai_assistant/models.py`.

- L7 `AgentIntent` (class) — Lifecycle record for a single agent action against the platform.
- L105 `__str__(self)` (method)
- L109 `AgentIntentEvent` (class) — Immutable audit log of every state transition on an AgentIntent.
- L139 `AgentMemory` (class)
- L184 `AgentRegistration` (class)
- L216 `save(self, *args, **kwargs)` (method)
- L222 `remaining_budget(self)` (method) — Decimal remaining budget, or None when no cap is configured.
- L228 `can_afford(self, amount)` (method) — Return True iff the configured budget can absorb `amount`.
- L236 `PromptTemplate` (class)
- L269 `AIExperiment` (class)
- L304 `AIInteraction` (class)
- L346 `DemandForecast` (class)
- L361 `MerchantInsight` (class)
- L397 `ProductEmbedding` (class) — Vector embedding for a product's description + key attributes.
- L423 `DynamicPriceRule` (class)
