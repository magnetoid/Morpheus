"""Agents contributed by agent_core.

Post-pivot (2026-05-23): the 5 specialist sub-agents (Concierge, Diagnostics,
Merchant Ops, Pricing, Content Writer) have been collapsed into a single
generic ``core.agents.builtin.Worker``. Linda fans out parallel Workers
via ``delegate.spawn_workers``; specialization is now a runtime composition
(skill bundle + objective text), not a class hierarchy.

The 5 specialist files are kept in this directory for one release as a
fallback — they're not registered. Remove them in Phase 3 once nothing
references them.
"""
from __future__ import annotations

from core.agents.builtin import Worker


def all_builtin_agents() -> list:
    return [Worker()]
