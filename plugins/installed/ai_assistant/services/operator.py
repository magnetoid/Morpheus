"""
AgentOperator — back-compat shim around `core.agents` runtime.

Historically this ran the Merchant Ops agent. Post-pivot (2026-05-23)
there is just one generic Worker, and this shim hands work to it.
External callers (proactive_agent_worker, scheduled jobs) keep working
unchanged. Prefer ``delegate.spawn_workers`` in new code.
"""
from __future__ import annotations

import logging
from typing import Any

from core.agents import agent_registry

logger = logging.getLogger('morpheus.ai.operator')


class AgentOperator:
    """Compatibility wrapper that hands an objective to the generic Worker."""

    def __init__(self, provider: str = '') -> None:
        self.provider = provider

    def run_workflow(self, objective: str) -> dict[str, Any]:
        """Run an objective through the generic Worker."""
        from plugins.installed.agent_core.services import run_agent

        if agent_registry.get_agent('worker') is None:
            return {
                'status': 'unavailable',
                'message': 'worker agent not registered (agent_core not active?)',
            }
        try:
            result = run_agent(
                agent_name='worker',
                user_message=objective,
                context={'source': 'proactive_agent_worker'},
            )
        except Exception as e:  # noqa: BLE001
            logger.error('AgentOperator.run_workflow failed: %s', e, exc_info=True)
            return {'status': 'failed', 'error': str(e)}
        return {
            'status': result.state,
            'run_id': result.run_id,
            'final_text': result.text,
            'tool_calls': result.tool_calls,
            'tokens': result.trace.prompt_tokens + result.trace.completion_tokens,
        }

    def execute_tool(self, tool_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Direct tool invocation (no LLM). Useful for tests + scripted automations."""
        tool = agent_registry.get_tool(tool_name)
        if tool is None:
            return {'error': f'Tool {tool_name} not found'}
        try:
            result = tool.invoke(kwargs or {})
        except Exception as e:  # noqa: BLE001
            return {'error': str(e)}
        return {'output': result.output}
