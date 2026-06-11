"""
In-memory trace of a single agent run.

The runtime appends a `TraceStep` for every observable event (system
prompt, user message, tool call, tool result, final answer). The plugin
`agent_core` mirrors this trace into the `AgentRun` / `AgentStep`
database tables and streams it to subscribers via SSE.

Trace lives only in memory while the run is active — persistence is the
plugin's job.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class TraceStep:
    kind: str  # 'system' | 'user' | 'assistant' | 'tool_call' | 'tool_result' | 'final' | 'error'
    content: str = ''
    name: str = ''  # tool name (when applicable)
    arguments: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class AgentTrace:
    run_id: str = ''
    steps: list[TraceStep] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Optional live subscriber — invoked synchronously after every push.
    subscriber: Callable[[TraceStep], None] | None = None

    def push(self, step: TraceStep) -> None:
        self.steps.append(step)
        if self.subscriber:
            try:  # noqa: SIM105
                self.subscriber(step)
            except Exception:  # noqa: BLE001, S110
                # Subscriber failure must not break the run.
                pass

    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'started_at': self.started_at.isoformat(),
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'steps': [
                {
                    'kind': s.kind,
                    'content': s.content,
                    'name': s.name,
                    'arguments': s.arguments,
                    'output': s.output,
                    'at': s.at.isoformat(),
                }
                for s in self.steps
            ],
        }
