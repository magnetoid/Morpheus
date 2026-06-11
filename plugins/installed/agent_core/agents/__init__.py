"""Agents contributed by agent_core.

Post-pivot (2026-05-23): the 5 specialist sub-agents (Concierge,
Diagnostics, Merchant Ops, Pricing, Content Writer) have been collapsed
into a single generic ``core.agents.builtin.Worker``. Specialization is
now a runtime composition (skill bundle + objective text), not a class
hierarchy. The specialist files have been deleted; their durable
behaviour lives on as registered Skills in the respective domain
plugins (`crm`, `seo`, `inventory`).
"""

from __future__ import annotations

from core.agents.builtin import Worker


def all_builtin_agents() -> list:
    return [Worker()]
