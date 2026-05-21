"""Linda's platform-health tools — surface circuit-breaker + ops state.

The merchant asks "is the platform healthy?" or "is OpenAI down right now?";
Linda calls one of these and gets a real answer instead of guessing from
the last error she happened to see in the log stream.

These are READ-ONLY tools — they introspect runtime state. Mutating breakers
(forcing reset, manually tripping) lives in a separate gated write tool.
"""
from __future__ import annotations

from core.assistant.tools.filesystem import ToolError, ToolResult, tool


@tool(
    name='platform.circuit_breakers',
    description=(
        'Return the live state of every named circuit breaker registered '
        'with the platform — useful when the merchant asks "is OpenAI down" '
        'or "why are payments slow". Each entry includes: name, state '
        '(closed | half_open | open), consecutive failures, how many '
        'seconds ago it tripped (if open), and its threshold + cooldown.'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}, 'additionalProperties': False},
)
def platform_circuit_breakers_tool(*, agent=None, context=None) -> ToolResult:
    try:
        from core.circuit_breaker import CircuitBreaker
    except Exception as exc:  # noqa: BLE001
        raise ToolError(f'circuit_breaker module not available: {exc}')

    snapshot = CircuitBreaker.snapshot()
    open_count = sum(1 for s in snapshot if s['state'] == 'open')
    half_open_count = sum(1 for s in snapshot if s['state'] == 'half_open')

    return ToolResult(output={
        'breakers': snapshot,
        'summary': {
            'total': len(snapshot),
            'open': open_count,
            'half_open': half_open_count,
            'closed': len(snapshot) - open_count - half_open_count,
        },
    })
