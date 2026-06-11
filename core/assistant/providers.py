"""LLM provider for the Assistant.

The Assistant deliberately does NOT depend on `core.agents.llm` so it can
boot even if the agent kernel fails to import. It re-uses the same
provider abstraction (lazy import) when available, but falls back to a
local mock so the chat window is always reachable.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.assistant')


def get_default_provider():
    """Return an LLM provider, or a mock if none is configured."""
    try:
        from core.agents.llm import get_llm_provider

        return get_llm_provider()
    except Exception as e:  # noqa: BLE001 — degrade gracefully
        logger.warning('assistant: agents.llm unavailable, using mock: %s', e)
        from core.assistant._mock_provider import MockAssistantProvider

        return MockAssistantProvider()
