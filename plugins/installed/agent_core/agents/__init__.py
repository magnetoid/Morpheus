"""Built-in agents shipped by agent_core."""
from __future__ import annotations

from plugins.installed.agent_core.agents.concierge import ConciergeAgent
from plugins.installed.agent_core.agents.diagnostics import DiagnosticsAgent
from plugins.installed.agent_core.agents.merchant_ops import MerchantOpsAgent
from plugins.installed.agent_core.agents.pricing import PricingAgent
from plugins.installed.agent_core.agents.content_writer import ContentWriterAgent


def all_builtin_agents() -> list:
    return [
        ConciergeAgent(),
        DiagnosticsAgent(),
        MerchantOpsAgent(),
        PricingAgent(),
        ContentWriterAgent(),
    ]
