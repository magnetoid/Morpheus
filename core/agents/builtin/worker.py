"""Worker — the single generic Morpheus agent.

Replaces the old 5-specialist hierarchy (Concierge, Merchant Ops,
Content Writer, Pricing, Diagnostics). One class. Behaviour shaped at
call time by:

  - **caller scopes** — Bearer-token or session permissions limit which
    platform tools resolve.
  - **skills** — optional `uses_skills=[…]` override at instance level
    narrows the tool set and prepends skill-specific prompt preludes
    (see `core.agents.skills`).
  - **objective** — the user-supplied task in the first turn.

Linda spawns Workers in parallel through `delegate.spawn_workers` and
collects results via `poll_workers` / `wait_for_workers`. Each run is
its own `AgentRun` row, so the audit trail and observability page work
unchanged.

Learning loop: at the end of a run, Worker can call `memory.remember`
(if any non-obvious fact was uncovered) so subsequent sessions inherit
that knowledge. Skills are the durable layer — every recurring pattern
should be promoted to a `Skill` at plugin load time.
"""
from __future__ import annotations

from core.agents.base import MorpheusAgent
from core.agents.prompts import Prompt, prompt_registry

prompt_registry.register(Prompt(
    name='worker',
    version=1,
    template=(
        "You are a Morpheus Worker — a generic background agent the platform "
        "spawns to carry out one focused objective on the merchant's behalf.\n\n"
        "Rules:\n"
        "  • Read the objective carefully. Pick the smallest set of tool calls "
        "that will satisfy it. Do not chat — act.\n"
        "  • Never invent numbers, IDs, slugs, prices, or counts — always call "
        "the appropriate tool and cite its output.\n"
        "  • Write operations (price changes, status changes, publishes) are "
        "gated by an explicit `confirmed=true` parameter. Do not pass it unless "
        "the objective itself authorises the change.\n"
        "  • When you finish, return a short structured report:\n"
        "      1. What you did (3–6 bullet points, tool-cited).\n"
        "      2. Anything surprising worth remembering for future sessions "
        "(call `memory.remember` if the merchant would benefit).\n"
        "      3. What you did NOT do and would defer to a human.\n"
        "  • Be terse. The orchestrator (Linda) reads your output verbatim."
    ),
    description='Generic worker prompt — used by every spawned Worker run.',
))


class Worker(MorpheusAgent):
    """The single generic Morpheus agent.

    Subclassing is NOT expected. To narrow behaviour, pass a `Skill` set
    when constructing the runtime, or filter the tool catalog before
    `runtime.run()`. Scope intersection happens automatically in
    `MorpheusAgent.get_tools()`.
    """
    name = 'worker'
    label = 'Worker'
    description = (
        'Generic background agent. Linda spawns these in parallel to carry '
        'out merchant objectives. One agent, any job — specialization '
        'happens via Skills, not subclasses.'
    )
    icon = 'cpu'
    audience = 'any'

    # Full scope set — actual tool access is bounded at runtime by:
    #   1. caller scopes (token or session-bound user permissions), and
    #   2. optional uses_skills=[…] filter.
    scopes = [
        'catalog.read', 'catalog.write',
        'cart.read', 'cart.write',
        'orders.read', 'orders.write',
        'inventory.read', 'inventory.write',
        'customers.read', 'customers.write',
        'content.read', 'content.write',
        'analytics.read',
        'seo.read', 'seo.write',
        'system.read', 'system.write',
    ]

    prompt_name = 'worker'
    temperature = 0.2
    max_tokens = 1500
    max_steps = 12
    requires_approval = False  # per-tool write gates still apply
