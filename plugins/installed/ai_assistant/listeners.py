"""Stub kept for backwards compatibility.

The earlier `proactive_agent_worker` Celery task and
`register_proactive_agents()` registration helper were never
called from `AIAssistantPlugin.ready()` and contained a typo
(`CUSTOMER_CREATED` doesn't exist on `MorpheusEvents` — the actual
constant is `CUSTOMER_REGISTERED`). Both have been removed.

The per-event agent runs that replaced them (order placed, customer
registered, cart abandoned, product created) were retired too: each handed
the all-scope Worker a vague objective and used nothing it produced.

Linda's Pulse covers proactive suggestions.
"""
