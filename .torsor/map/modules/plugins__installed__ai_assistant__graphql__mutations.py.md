---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/ai_assistant/graphql/mutations.py

Symbols in `plugins/installed/ai_assistant/graphql/mutations.py`.

- L22 `AgentIntentReceipt` (class)
- L30 `AgentIntentType` (class)
- L39 `ProposeIntentInput` (class)
- L49 `_resolve_agent(info)` (function) — Pull the AgentRegistration for the current request, or raise.
- L67 `_load_intent(info, intent_id: str)` (function)
- L88 `AIAssistantMutationExtension` (class)
- L90 `propose_agent_intent(self, info: strawberry.Info, input: ProposeIntentInput)` (method)
- L130 `authorize_agent_intent(self, info: strawberry.Info, intent_id: strawberry.ID, note: str='')` (method)
- L151 `reject_agent_intent(self, info: strawberry.Info, intent_id: strawberry.ID, reason: str='')` (method)
