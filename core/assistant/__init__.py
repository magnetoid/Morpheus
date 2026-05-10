"""
core.assistant — Linda, the hard-coded staff AI assistant.

Distinct from `core.agents`. The agents kernel is a programming surface
that plugins can contribute to. The Assistant is a single, always-available
operator that survives plugin failure, knows the whole platform, and can
delegate to any registered agent.

Why hardcoded:

* It must come up even when a plugin import explodes — so the merchant
  always has a window to ask "what just broke?".
* It needs system-level scopes (filesystem read/write, DB introspection,
  log search) that no plugin should ever hold.
* It is the *one* assistant a merchant talks to. Everything else
  (Concierge, Merchant Ops, Support, Pricing, etc.) is a specialised
  agent the Assistant delegates to.

Public surface:

    from core.assistant import (
        Assistant, run_assistant, AssistantMessage,
        get_default_provider, get_default_tools,
    )
"""
from __future__ import annotations

from core.assistant.runtime import (
    Assistant,
    AssistantMessage,
    AssistantRunResult,
    run_assistant,
)
from core.assistant.persistence import (
    AssistantStore,
    get_default_store,
)
from core.assistant.providers import get_default_provider
from core.assistant.tools import get_default_tools

__all__ = [
    'Assistant',
    'AssistantMessage',
    'AssistantRunResult',
    'AssistantStore',
    'get_default_provider',
    'get_default_store',
    'get_default_tools',
    'run_assistant',
]
