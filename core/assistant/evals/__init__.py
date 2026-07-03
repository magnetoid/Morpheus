"""Evals harness — golden tasks that measure whether Linda actually works.

Every prompt/skill/memory change can silently regress the assistant; this
harness makes "smarter" measurable. Tasks live in ``golden.json`` next to
this module; each declares a prompt and checks over the final answer and
the tool trace. Run with::

    python manage.py run_assistant_evals            # configured provider
    python manage.py run_assistant_evals --task product-count

CI runs the harness's own unit tests against the scripted mock provider
(the harness must work); scoring Linda against golden tasks needs a real
provider and is a pre-ship ritual, not a CI gate (cost).

Task schema (all checks optional; a task passes when every present check
passes and the run completed):

    {"name": "product-count",
     "prompt": "How many products do we have?",
     "mode": "general",
     "checks": {"tool_called": "products.count",
                "answer_matches": "\\\\d+",
                "answer_not_contains": ["as an AI", "I cannot"]}}
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

GOLDEN_PATH = Path(__file__).parent / 'golden.json'


@dataclass(slots=True)
class EvalResult:
    name: str
    ok: bool
    failures: list[str] = field(default_factory=list)
    answer: str = ''
    tools_used: list[str] = field(default_factory=list)
    duration_ms: int = 0


def load_tasks(path: Path | None = None) -> list[dict]:
    raw = json.loads((path or GOLDEN_PATH).read_text())
    if not isinstance(raw, list):
        raise ValueError('golden tasks file must be a JSON array')
    return raw


def run_task(task: dict, *, provider=None) -> EvalResult:
    """Run one golden task through the real Assistant loop and grade it."""
    from core.assistant.runtime import Assistant

    name = task.get('name') or 'unnamed'
    checks = task.get('checks') or {}
    kwargs = {'provider': provider} if provider is not None else {}
    assistant = Assistant(**kwargs)

    started = time.monotonic()
    answer = ''
    state = 'failed'
    tools_used: list[str] = []
    for event in assistant.stream(
        message=task['prompt'],
        conversation_key=f'eval-{name}-{uuid.uuid4().hex[:8]}',
        context={'mode': task.get('mode') or 'general'},
    ):
        kind = event.get('type')
        if kind == 'tool_call_started':
            tools_used.append(event.get('name') or '')
        elif kind in ('final', 'error'):
            answer = event['result'].text or ''
            state = event['result'].state
    duration_ms = int((time.monotonic() - started) * 1000)

    failures: list[str] = []
    if state != 'completed':
        failures.append(f'run state = {state}')
    tool = checks.get('tool_called')
    if tool and tool not in tools_used:
        failures.append(f'expected tool {tool!r}; used {tools_used or "none"}')
    pattern = checks.get('answer_matches')
    if pattern and not re.search(pattern, answer, re.IGNORECASE):
        failures.append(f'answer does not match /{pattern}/')
    for needle in checks.get('answer_not_contains') or []:
        if needle.lower() in answer.lower():
            failures.append(f'answer contains forbidden {needle!r}')

    return EvalResult(
        name=name,
        ok=not failures,
        failures=failures,
        answer=answer[:500],
        tools_used=tools_used,
        duration_ms=duration_ms,
    )


def run_all(*, provider=None, only: str = '', path: Path | None = None) -> list[EvalResult]:
    tasks = load_tasks(path)
    if only:
        tasks = [t for t in tasks if t.get('name') == only]
    return [run_task(t, provider=provider) for t in tasks]
