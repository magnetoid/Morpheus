---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/ai_assistant/graphql/mutations.py

Symbols in `plugins/installed/ai_assistant/graphql/mutations.py`.

- L21 `AgentIntentReceipt` (class)
- L29 `AgentIntentType` (class)
- L38 `ProposeIntentInput` (class)
- L48 `_resolve_agent(info)` (function) — Pull the AgentRegistration for the current request, or raise.
- L61 `_load_intent(info, intent_id: str)` (function)
- L77 `AIAssistantMutationExtension` (class)
- L80 `propose_agent_intent(self, info: strawberry.Info, input: ProposeIntentInput)` (method)
- L120 `authorize_agent_intent(self, info: strawberry.Info, intent_id: strawberry.ID, note: str='')` (method)
- L141 `reject_agent_intent(self, info: strawberry.Info, intent_id: strawberry.ID, reason: str='')` (method)
