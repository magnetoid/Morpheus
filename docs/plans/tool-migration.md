# Agent Tool Migration (D3) — Design + Status

Goal: move the agent-tool query layer out of `core/` into the plugins that own
the models, so `core/assistant/tools/*` stops importing `plugins.installed.*`.

## Mechanism (proven, in use)

A tool's implementation lives in its owning plugin's `agent_tools.py` +
`contribute_agent_tools()`. Core's **curated** `get_default_tools()`
(`core/assistant/tools/__init__.py`) sources it **by name** from the agent
registry:

```python
from core.agents import agent_registry
tools += [t for t in (agent_registry.get_tool(n) for n in _migrated_names) if t]
```

No core→plugin import; tool names stay stable (Linda's prompts/skills keep
resolving); disabling the owning plugin removes the tool from Linda. Established
2026-06-17.

## Status

**Reads — DONE (13 tools).** `orders.search/get`, `products.search/get`,
`customers.search/get`, `media.search`, `metafields.list_for`, `markets.list`,
`analytics.summary/top_products` (→ orders, they aggregate Order/OrderItem),
`cms.pages`, `email.templates`. `core/assistant/tools/ecommerce.py` now holds
ONLY `settings.list` + `db.describe_model` (generic, no plugin model — they stay
in core, correctly). This captured the bulk of the core→plugin coupling.

**Writes — BLOCKED on a design decision (do NOT grind).** Attempting to migrate
`ecommerce_writes.py` surfaced that the write tools are **triplicated /
name-collided** across two parallel tool systems:

| Tool name | Linda's copy (`core/assistant/tools/ecommerce_writes.py`) | Worker's copy (`plugins/installed/agent_core/tools/orders.py` etc.) |
|---|---|---|
| `orders.cancel` | `confirmed=False` inline gate (chat: ask → re-call `confirmed=True`) | `requires_approval=True` (runtime approval-flow gate); **no `confirmed` param** |
| `orders.update_status` / `orders.add_note` | confirmed-gate | (agent_core has `mark_fulfilled`/`mark_shipped`/`mark_refunded` — overlapping, not identical) |

The two copies are **intentionally different** — Linda gates writes inline in
chat (`confirmed`), the Worker gates them via the runtime `approval_check`. They
share tool **names** but not behavior. So:

- Naively moving Linda's `ecommerce_writes` copy into a plugin makes it collide
  in the registry with agent_core's copy (`get_tool('orders.cancel')` becomes
  ambiguous). This is what the 2026-06-18 write attempt hit; it was reverted.
- The reads had no such split (one impl, identical for both callers), which is
  why they migrated cleanly.

## The real decision (for whoever picks this up)

Write migration ≠ tool migration; it's **Linda/Worker write-tool
consolidation**. Options:

1. **Unify (clean, medium-high risk).** One write tool per action in the owning
   plugin, carrying BOTH gates: an inline `confirmed` param (for chat callers)
   AND `requires_approval=True` (for runtime-approval callers). Both Linda
   (registry-sourced by name) and the Worker (agent_registry) use the same
   object. Delete both `ecommerce_writes.py` and the overlapping
   `agent_core/tools/*` writes. **Verify:** the runtime tolerates a tool with a
   `confirmed` param AND `requires_approval`; Linda's ask→confirm UX still works;
   the Worker's approval flow still works. Do it **per-domain, orders first,
   with tests** — never big-bang.

2. **Defer (recommended for now).** The read migration already removed most of
   the core→plugin tool coupling. The write duplication is a pre-existing
   architectural wart (two tool systems predating D3), and the lazy imports in
   `ecommerce_writes.py` are the same "acceptable, guarded" pattern Phase 0
   signed off on. Unifying the Linda/Worker tool systems is a larger project
   than D3; pull it out as its own initiative when there's appetite, rather than
   grinding it tool-by-tool under D3.

**Recommendation: option 2** — mark D3 substantially complete with reads done,
and spin "Linda/Worker write-tool unification" out as a separate, deliberately-
scoped effort. Do not migrate `ecommerce_writes.py` piecemeal; it will collide.

## Files
- `core/assistant/tools/__init__.py` (`get_default_tools`, `_migrated_names`)
- `core/assistant/tools/ecommerce.py` (now reads-only: settings.list, db.describe_model)
- `core/assistant/tools/ecommerce_writes.py` (Linda's confirmed-gated writes — unmigrated)
- `plugins/installed/agent_core/tools/*.py` (the Worker's tool set — the other copy)
- per-plugin `agent_tools.py` (orders/catalog/customers/media/metafields/markets/cms)
