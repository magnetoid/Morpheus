"""Who wrote a piece of text: one of the store's own AI agents, or someone else.

Art. 50 of the EU AI Act asks that text a model generates be marked as such. A
tool that writes product text calls :func:`mark_ai_written` with
:func:`ai_author`'s answer; the AI content app stores and publishes the mark.

Only the store's own agents count. Linda's turns reach the tools through the MCP
edge with ``context['source'] == 'linda'`` (an external agent asking Janus goes
the same way), and a Worker run passes its agent. A plain API token call is
anonymous: it may be a product-information system copying text a person wrote,
so nothing is claimed for it.
"""

from __future__ import annotations

from typing import Any


def ai_author(agent: Any = None, context: Any = None) -> str:
    """'linda', 'worker', or '' when no agent of this store wrote the call."""
    if isinstance(context, dict) and context.get('source') == 'linda':
        return 'linda'
    if agent is not None:
        return 'worker'
    return ''


def mark_ai_written(instance: Any, fields, source: str) -> None:
    """Record that ``source`` wrote ``fields`` of ``instance``. A no-op without a source."""
    fields = [f for f in fields or () if f]
    if not source or instance is None or not fields:
        return
    from core.hooks import MorpheusEvents, hook_registry

    hook_registry.fire(
        MorpheusEvents.AI_CONTENT_WRITTEN, instance=instance, fields=fields, source=source
    )
