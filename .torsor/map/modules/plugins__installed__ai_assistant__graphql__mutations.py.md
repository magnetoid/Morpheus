---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/graphql/mutations.py

Symbols in `plugins/installed/ai_assistant/graphql/mutations.py`.

- L20 `AgentIntentReceipt` (class)
- L28 `AgentIntentType` (class)
- L37 `ProposeIntentInput` (class)
- L47 `_resolve_agent(info)` (function) — Pull the AgentRegistration for the current request, or raise.
- L65 `_load_intent(info, intent_id: str)` (function)
- L86 `AIAssistantMutationExtension` (class)
- L88 `propose_agent_intent(self, info: strawberry.Info, input: ProposeIntentInput)` (method)
- L128 `authorize_agent_intent(self, info: strawberry.Info, intent_id: strawberry.ID, note: str='')` (method)
- L149 `reject_agent_intent(self, info: strawberry.Info, intent_id: strawberry.ID, reason: str='')` (method)
