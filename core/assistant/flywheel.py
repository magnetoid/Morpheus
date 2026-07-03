"""Tool-gap flywheel — Linda drafts tools for capabilities she kept missing.

Weekly (beat, Monday 06:30 UTC): read the `tool_gap.*` memories the
reflection loop accumulates, and for every gap observed at least twice,
have the LLM draft a small @tool module. The draft goes through the exact
same path as `code.draft_tool` (static safety scan → CodeProposal row) and
lands in the superuser approval queue at /dashboard/assistant/proposals/.
Propose-only: nothing here executes generated code or touches the repo.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger('morpheus.assistant.flywheel')

_SKIP_PROVIDERS = ('mock', 'unconfigured')
_MIN_SEEN = 2
_MAX_DRAFTS_PER_RUN = 2

_DRAFT_SYSTEM = (
    'You write ONE new agent tool for the Morpheus commerce platform (Django). '
    'Reply with ONLY a complete Python module, no prose and no markdown fences.\n'
    'Pattern to follow exactly:\n'
    '  from core.assistant.tools.filesystem import ToolError, ToolResult, tool\n'
    '  @tool(name="<dotted.name>", description="...", scopes=["<area>.read"],\n'
    '        schema={"type": "object", "properties": {...}, "required": [...]})\n'
    '  def <name>_tool(*, ...) -> ToolResult:\n'
    '      ...\n'
    '      return ToolResult(output={...})\n'
    'Rules: prefer read-only scopes; import Django models lazily inside the '
    'function; validate inputs and raise ToolError on bad ones; no filesystem, '
    'network, subprocess, or eval; keep it under 80 lines.'
)


def _strip_fences(text: str) -> str:
    m = re.search(r'```(?:python)?\s*\n(.*?)```', text or '', re.DOTALL)
    return (m.group(1) if m else (text or '')).strip()


def _seen_count(value: str) -> int:
    m = re.match(r'seen=(\d+)', value or '')
    return int(m.group(1)) if m else 1


def run_tool_gap_flywheel(*, provider=None) -> dict:
    """Draft proposals for repeat tool gaps. Returns a status dict; never raises."""
    try:
        from core.assistant.models import CodeProposal, LindaMemory

        gaps = []
        for row in LindaMemory.objects.filter(scope='merchant', key__startswith='tool_gap.'):
            if _seen_count(row.value) >= _MIN_SEEN:
                gaps.append(row)
        if not gaps:
            return {'drafted': 0, 'note': 'no repeat tool gaps'}

        if provider is None:
            from core.assistant.providers import get_default_provider

            provider = get_default_provider()
            if getattr(provider, 'name', '') in _SKIP_PROVIDERS:
                return {'skipped': 'no provider configured'}

        from core.agents.llm import LLMMessage
        from core.assistant.tools.code import code_draft_tool

        drafted = []
        for row in gaps:
            name = row.key.removeprefix('tool_gap.').replace('_', '-')[:120]
            if CodeProposal.objects.filter(name=name).exists():
                continue  # already proposed (any status) — never re-draft
            if len(drafted) >= _MAX_DRAFTS_PER_RUN:
                break
            description = re.sub(r'^seen=\d+\s*·\s*', '', row.value or '')
            resp = provider.respond(
                messages=[
                    LLMMessage(role='system', content=_DRAFT_SYSTEM),
                    LLMMessage(
                        role='user',
                        content=(
                            f'Missing capability (observed {_seen_count(row.value)}× '
                            f'in agent runs): {description}'
                        ),
                    ),
                ],
                tools=None,
                temperature=0.1,
                max_tokens=1500,
            )
            source = _strip_fences(getattr(resp, 'text', ''))
            if not source:
                continue
            out = code_draft_tool.handler(
                name=name,
                source=source,
                rationale=(
                    f'Auto-drafted from tool gap "{description}" '
                    f'(observed {_seen_count(row.value)}× by the reflection loop). '
                    'Review at /dashboard/assistant/proposals/.'
                ),
            ).output
            drafted.append({'name': out['name'], 'passed': out['passed']})

        logger.info('flywheel: drafted %d proposal(s): %s', len(drafted), drafted)
        return {'drafted': len(drafted), 'proposals': drafted}
    except Exception as e:  # noqa: BLE001 — beat task must never crash-loop
        logger.warning('flywheel: failed: %s', e, exc_info=True)
        return {'skipped': str(e)[:200]}
