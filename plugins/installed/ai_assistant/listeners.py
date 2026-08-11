"""Stub kept for backwards compatibility.

The earlier `proactive_agent_worker` Celery task and
`register_proactive_agents()` registration helper were never
called from `AIAssistantPlugin.ready()` and contained a typo
(`CUSTOMER_CREATED` doesn't exist on `MorpheusEvents` — the actual
constant is `CUSTOMER_REGISTERED`). Both have been removed.

The same use-case is now covered by the focused hook handlers
already wired in ``app.py``:

  - ``on_order_placed`` → ``update_recommendations_after_order``
  - ``on_customer_registered`` → ``initialize_customer_memory``
  - ``on_cart_abandoned`` → ``generate_cart_recovery``

Linda's Pulse picks up the proactive-suggestion role on top of those.
"""
