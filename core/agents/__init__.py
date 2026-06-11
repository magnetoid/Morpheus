"""
core.agents — the kernel agent layer.

This module is a peer of `core.hooks` and `plugins.base`. It defines the
primitives every Morpheus agent uses: agent base class, tool dataclass,
LLM provider abstraction, runtime loop, registry, memory store, prompts,
policies, and trace.

The plugin `agent_core` wires this kernel into the database, GraphQL,
the dashboard, and the streaming endpoint. Built-in agents (Concierge,
Merchant Ops, Pricing, Content Writer) live in that plugin.

Public surface:

    from core.agents import (
        MorpheusAgent, agent_registry,
        Tool, ToolResult, tool,
        AgentRuntime,
        LLMProvider, get_llm_provider,
        AgentTrace,
        AgentEvents,
    )
"""

from __future__ import annotations

from core.agents.base import MorpheusAgent
from core.agents.events import AgentEvents
from core.agents.llm import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMToolCall,
    MockLLMProvider,
    get_llm_provider,
)
from core.agents.policies import (
    AgentPolicyError,
    BudgetExceeded,
    ScopeDenied,
    enforce_policy,
)
from core.agents.prompts import Prompt, prompt_registry
from core.agents.registry import agent_registry
from core.agents.runtime import AgentRuntime, RunResult
from core.agents.skills import Skill, skill_registry
from core.agents.tools import Tool, ToolError, ToolResult, tool
from core.agents.trace import AgentTrace, TraceStep

__all__ = [
    'AgentEvents',
    'AgentPolicyError',
    'AgentRuntime',
    'AgentTrace',
    'BudgetExceeded',
    'LLMMessage',
    'LLMProvider',
    'LLMResponse',
    'LLMToolCall',
    'MockLLMProvider',
    'MorpheusAgent',
    'Prompt',
    'RunResult',
    'ScopeDenied',
    'Skill',
    'Tool',
    'ToolError',
    'ToolResult',
    'TraceStep',
    'agent_registry',
    'enforce_policy',
    'get_llm_provider',
    'prompt_registry',
    'skill_registry',
    'tool',
]
