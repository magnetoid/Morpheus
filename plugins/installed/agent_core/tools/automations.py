"""Automations tools — Linda lists, schedules, pauses, resumes, runs and deletes them.

The same actions as the Automations page (`/dashboard/agents/background/`),
through the same functions in `agent_core/scheduler.py`. A new automation always
runs on Linda, as the merchant who asked for it, in its own chat; it reads and
reports and never changes the store (`linda_automations.py`).

Only a merchant's own chat with Linda may use them. An automation runs with
Linda's read profile as its owner, so one created by an external agent's token
or by another automation would read what that caller may not, and its answer
(`automations.list` shows it) would hand the result back. Every change needs the
merchant's yes, like every write.
"""

from __future__ import annotations

import uuid

from morpheus.core import ToolError, ToolResult, tool
from plugins.installed.agent_core.scheduler import scheduled_runs_on

_ID = {
    'type': 'object',
    'properties': {
        'automation_id': {
            'type': 'string',
            'description': "The automation's id, from automations.list.",
        }
    },
    'required': ['automation_id'],
}

_OFF_NOTE = (
    'Scheduled runs are off: they need "Enable autonomous operator" (Settings → AI). '
    'Run now works either way.'
)


def _merchant(context, *, changes: bool):
    """The staff member whose chat this is; ToolError for any other caller."""
    from core.assistant import gates

    ctx = context or {}
    key = str(ctx.get('conversation_key') or '')
    user = ctx.get('user')
    if gates.is_external_key(key):
        raise ToolError(
            "Automations are the store staff's own: an external agent cannot see or change them."
        )
    if (
        ctx.get('source') != 'linda'
        or not key
        or not getattr(user, 'is_active', False)
        or not getattr(user, 'is_staff', False)
    ):
        raise ToolError(
            'Automations are managed from a chat with Linda or on the Automations page.'
        )
    if changes and gates.is_automation_key(key):
        raise ToolError(
            'A scheduled automation cannot change automations. Say what you would change; '
            'the merchant can ask for it in a chat.'
        )
    from core.authz import check

    # The Automations page needs `system.write` to be seen at all.
    if not check(user, 'system.write', target='automations'):
        raise ToolError('Your role does not allow managing automations.')
    return user


def _automation(automation_id: str):
    from plugins.installed.agent_core.models import BackgroundAgent

    try:
        pk = uuid.UUID(str(automation_id))
    except ValueError:
        pk = None
    bg = BackgroundAgent.objects.filter(pk=pk).first() if pk else None
    if bg is None:
        raise ToolError(f'No automation has the id {automation_id!r}; automations.list shows them.')
    return bg


def _row(bg, user) -> dict:
    return {
        'id': str(bg.pk),
        'name': bg.name,
        'runs_as': 'Linda' if bg.engine == bg.ENGINE_LINDA else f'Worker agent {bg.agent_name}',
        'what': bg.prompt[:300],
        'schedule': bg.schedule_label,
        'state': bg.state,
        'last_run_at': bg.last_run_at.isoformat() if bg.last_run_at else None,
        'next_run_at': bg.next_run_at.isoformat() if bg.next_run_at else None,
        'last_error': (bg.last_error or '')[:300],
        'last_answer': (bg.last_output or '')[:600],
        'yours': bg.created_by_id == user.pk,
    }


def _with_switch(out: dict) -> dict:
    out['scheduled_runs_on'] = scheduled_runs_on()
    if not out['scheduled_runs_on']:
        out['note'] = _OFF_NOTE
    return out


@tool(
    name='automations.list',
    description=(
        "List the store's automations: jobs Linda runs on a schedule, with each one's "
        'schedule, state, next run and the start of its last answer (the full answer is '
        'in its own chat, under Chats).'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_automations_tool(*, context=None) -> ToolResult:
    from plugins.installed.agent_core.models import BackgroundAgent

    user = _merchant(context, changes=False)
    rows = [_row(bg, user) for bg in BackgroundAgent.objects.order_by('-updated_at')[:50]]
    return ToolResult(
        output=_with_switch({'automations': rows}), display=f'{len(rows)} automations'
    )


@tool(
    name='automations.create',
    description=(
        'Schedule a recurring job for Linda, e.g. "every Monday at 9, tell me what is low on '
        'stock". It runs as the merchant, answers in its own chat (under Chats) and never '
        'changes the store: it reports, and lists any change it recommends. Give a schedule: '
        '`cron` (five fields on the store clock — minute hour day-of-month month day-of-week, '
        'e.g. "0 9 * * 1-5" for weekdays at 09:00) or `every_minutes` (15 or more). '
        "Needs the merchant's yes."
    ),
    scopes=['system.write'],
    requires_approval=True,
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string', 'description': 'A short label, e.g. "Monday stock check".'},
            'prompt': {
                'type': 'string',
                'description': 'What Linda does on each run, written as a request to her.',
            },
            'cron': {'type': 'string', 'description': 'Five cron fields, store time.'},
            'every_minutes': {'type': 'integer', 'minimum': 15},
        },
        'required': ['name', 'prompt'],
    },
)
def create_automation_tool(
    *, name: str, prompt: str, cron: str = '', every_minutes: int = 0, context=None
) -> ToolResult:
    from plugins.installed.agent_core.scheduler import create_automation, min_interval_s

    user = _merchant(context, changes=True)
    if cron and every_minutes:
        raise ToolError('Give one schedule, not both: `cron` or `every_minutes`.')
    if not cron and not every_minutes:
        raise ToolError(
            'Give a schedule: `cron` (e.g. "0 9 * * 1-5") or `every_minutes` (15 or more).'
        )
    floor_minutes = min_interval_s('linda') // 60
    if every_minutes and int(every_minutes) < floor_minutes:
        raise ToolError(f'Linda automations run at most every {floor_minutes} minutes.')
    try:
        bg = create_automation(
            name=name,
            prompt=prompt,
            owner=user,
            interval_seconds=int(every_minutes or 60) * 60,
            cron=cron,
        )
    except ValueError as e:
        raise ToolError(str(e)) from e
    out = _row(bg, user)
    out['chat'] = 'Each run answers in its own chat, under Chats.'
    return ToolResult(
        output=_with_switch(out), display=f'Scheduled "{bg.name}": {bg.schedule_label}'
    )


@tool(
    name='automations.pause',
    description='Pause an automation: it stops running on its schedule until resumed.',
    scopes=['system.write'],
    requires_approval=True,
    schema=_ID,
)
def pause_automation_tool(*, automation_id: str, context=None) -> ToolResult:
    from plugins.installed.agent_core.scheduler import pause

    user = _merchant(context, changes=True)
    bg = _automation(automation_id)
    pause(bg)
    return ToolResult(output=_row(bg, user), display=f'Paused "{bg.name}"')


@tool(
    name='automations.resume',
    description=(
        'Resume a paused automation (also clears its failure count). It runs again from '
        'its next scheduled time.'
    ),
    scopes=['system.write'],
    requires_approval=True,
    schema=_ID,
)
def resume_automation_tool(*, automation_id: str, context=None) -> ToolResult:
    from plugins.installed.agent_core.scheduler import resume

    user = _merchant(context, changes=True)
    bg = _automation(automation_id)
    resume(bg)
    return ToolResult(output=_with_switch(_row(bg, user)), display=f'Resumed "{bg.name}"')


@tool(
    name='automations.run_now',
    description=(
        "Run a Linda automation once now, outside its schedule. It answers in the automation's "
        'own chat in a few minutes; this call does not wait for it.'
    ),
    scopes=['system.write'],
    requires_approval=True,
    schema=_ID,
)
def run_automation_now_tool(*, automation_id: str, context=None) -> ToolResult:
    from plugins.installed.agent_core.scheduler import fire

    _merchant(context, changes=True)
    bg = _automation(automation_id)
    if bg.engine != bg.ENGINE_LINDA:
        # A Worker run happens inside the request, which a chat turn cannot wait for.
        raise ToolError('This automation runs a Worker agent; run it from the Automations page.')
    result = fire(bg)
    if not result.get('ok'):
        raise ToolError(f'"{bg.name}" is already running.')
    return ToolResult(
        output={'queued': True, 'id': str(bg.pk), 'name': bg.name},
        display=f'Running "{bg.name}" now',
    )


@tool(
    name='automations.delete',
    description='Delete an automation for good. Its chat stays under Chats.',
    scopes=['system.write'],
    requires_approval=True,
    schema=_ID,
)
def delete_automation_tool(*, automation_id: str, context=None) -> ToolResult:
    _merchant(context, changes=True)
    bg = _automation(automation_id)
    name = bg.name
    bg.delete()
    return ToolResult(output={'deleted': name}, display=f'Deleted "{name}"')
