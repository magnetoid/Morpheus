"""Self-contained mock provider so the Assistant runs without the agents kernel."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _Resp:
    text: str = ''
    tool_calls: list = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = 'assistant-mock'

    @property
    def is_tool_call(self) -> bool:
        return bool(self.tool_calls)


class MockAssistantProvider:
    name = 'assistant-mock'
    model = 'assistant-mock'

    def respond(self, *, messages, tools=None, temperature=0.3, max_tokens=1024):
        last_user = next(
            (m.content for m in reversed(messages or []) if getattr(m, 'role', '') == 'user'),
            '',
        )
        return _Resp(text=f'(mock) Got: {last_user[:200]}')
