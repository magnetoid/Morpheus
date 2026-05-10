"""Diagnostics — the sub-agent Linda delegates to for filesystem reads,
log searches, system info, and plugin lifecycle.

Splitting these tools out of Linda's primary surface keeps her tool
catalog under the ~30-tool ceiling at which selection accuracy degrades
(per Shopify Sidekick's "Death by a Thousand Instructions" findings).
Linda invokes this agent through ``delegate.invoke_agent('diagnostics',
...)`` — same code path as the other delegated agents.
"""
from __future__ import annotations

from core.agents import MorpheusAgent, Prompt, prompt_registry

prompt_registry.register(Prompt(
    name='diagnostics',
    version=1,
    template=(
        'You are the Diagnostics agent. You answer operator questions '
        'that need filesystem reads, log searches, system info, or '
        'plugin lifecycle (list / enable / disable). You return precise, '
        'tool-cited answers. Plugin disable is destructive — never call '
        'it without explicit operator confirmation; surface what would '
        'change first.'
    ),
))


class DiagnosticsAgent(MorpheusAgent):
    name = 'diagnostics'
    label = 'Diagnostics'
    description = (
        'Filesystem reads, log searches, system info, plugin lifecycle. '
        "Linda delegates here when an operator needs the platform's "
        'guts inspected.'
    )
    icon = 'wrench'
    audience = 'merchant'
    scopes = [
        'system.read',
        'system.write',  # plugins.enable / disable carry this scope
    ]
    prompt_name = 'diagnostics'
    temperature = 0.1
    max_tokens = 1200
    max_steps = 8
    requires_approval = False  # plugins.disable already prompts the operator
