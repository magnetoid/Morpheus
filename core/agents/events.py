"""Event names emitted by the agent runtime.

These ride the same `core.hooks.hook_registry` bus as the rest of the
platform, so any plugin can observe / veto / transform agent activity.
"""

from __future__ import annotations


class AgentEvents:
    # Lifecycle
    RUN_STARTED = 'agent.run.started'
    RUN_STEP = 'agent.run.step'
    RUN_COMPLETED = 'agent.run.completed'
    RUN_FAILED = 'agent.run.failed'
    RUN_CANCELLED = 'agent.run.cancelled'

    # Tools
    TOOL_CALLING = 'agent.tool.calling'  # filter — handlers may veto
    TOOL_CALLED = 'agent.tool.called'
    TOOL_FAILED = 'agent.tool.failed'

    # Approvals
    STEP_APPROVAL_REQUIRED = 'agent.step.approval_required'
    STEP_APPROVED = 'agent.step.approved'
    STEP_REJECTED = 'agent.step.rejected'

    # Memory
    MEMORY_WRITTEN = 'agent.memory.written'
    MEMORY_READ = 'agent.memory.read'

    # Autonomy gate — filter, value=bool (starts False). The background-agent
    # scheduler consults this before any PROACTIVE run; a subscriber flips it
    # True to enable autonomy. With no subscriber (e.g. ai_assistant disabled)
    # it stays False, so proactive runs are opt-in / fail-safe-off. Manual
    # "run now" (scheduler.fire) is NOT gated — it's an explicit human action.
    AUTONOMY_ENABLED = 'agent.autonomy_enabled'  # filter
