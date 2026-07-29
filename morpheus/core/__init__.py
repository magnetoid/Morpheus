"""Core-app SDK — the kernel API a plugin consumes from Morpheus core.

One of the three project SDKs (torsor ADR 0035 /
``docs/plans/sdk-restructure-2026-07.md``). Import the kernel from here instead of
reaching into ``core.*`` directly::

    from morpheus.core import events, hooks, MorpheusEvents
    from morpheus.core import tool, ToolResult, ToolError, agent_registry
    from morpheus.core import record_ai_decision, Money, money_str, site_base_url, absolutize

``events`` is the module-level constant mirror (``events.ORDER_PLACED``);
``MorpheusEvents`` is the same constants as a class, for code that imported it from
``core.hooks``. Additive facade — existing ``from core.hooks import …`` /
``from core.agents import …`` still work; this is the canonical door going forward,
adopted per ADR 0035.
"""

from __future__ import annotations

from djmoney.money import Money

from core.agents import ToolError, ToolResult, agent_registry, tool
from core.audit.services import record_ai_decision
from core.hooks import MorpheusEvents, hook_registry
from core.money import money_str
from core.utils.site import absolutize, site_base_url

# The event-name mirror + registry-access helpers (existing submodules).
from morpheus import events, hooks

__all__ = [
    'events',
    'hooks',
    'MorpheusEvents',
    'hook_registry',
    'tool',
    'ToolResult',
    'ToolError',
    'agent_registry',
    'record_ai_decision',
    'Money',
    'money_str',
    'site_base_url',
    'absolutize',
]
