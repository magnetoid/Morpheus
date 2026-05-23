"""Built-in agents that live in core (no plugin dependency).

After the agent_core collapse (see docs/plans/agent-core-into-core.md),
there is just one canonical agent: the generic Worker. Specialization
is handled at call time via Skills + caller scopes, not via class
hierarchy.
"""
from __future__ import annotations

from core.agents.builtin.worker import Worker

__all__ = ['Worker']
