"""Run a Linda automation: one Janus turn for its owner, in its own conversation.

Automations is the store's one scheduler (owner's call, 2026-10-10: "automations
is cron"). A Linda automation runs as its owner — the staff member who created
it — in the conversation ``user:<owner>:auto:<id>``, which is listed under Chats,
and its answer is kept on the row. It runs from a Celery worker, which has no
web server on loopback, so the turn reaches the store's tools by the store's
public address (``mcp_public``).

It can never change the store: nobody is there to approve, and the gate refuses
consent in an automation's conversation (core/assistant/gates.py). Linda says
what she would change; the merchant asks for it in a chat.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from core.assistant.runtime import Assistant

logger = logging.getLogger('morpheus.agent_core.automations')

PREAMBLE = (
    'This is the scheduled automation "{name}". Nobody is reading live and nobody can '
    'approve a change now: read what you need, report what you find, and list any change '
    'you recommend instead of making it.\n\n'
)


def run_by_id(automation_id: str) -> str:
    from plugins.installed.agent_core.models import BackgroundAgent

    bg = BackgroundAgent.objects.filter(pk=automation_id).first()
    return run(bg) if bg is not None else 'missing'


def run(bg) -> str:
    """One run. Returns 'completed', 'failed' or 'no_owner'.

    Releases the run lock ``scheduler.fire()`` took, whatever happens.
    """
    from plugins.installed.agent_core.scheduler import clear_running

    try:
        return _run(bg)
    finally:
        clear_running(bg)


def _run(bg) -> str:
    from core.assistant.gates import automation_key
    from core.assistant.models import AssistantConversation

    started = timezone.now()
    owner = bg.created_by
    if owner is None or not owner.is_active or not owner.is_staff:
        _record(bg, started, error='This automation has no active staff owner to run as.')
        return 'no_owner'

    key = automation_key(owner.pk, bg.pk)
    AssistantConversation.objects.get_or_create(
        key=key, defaults={'user': owner, 'title': f'Automation: {bg.name}'[:200]}
    )
    text, error = '', ''
    try:
        for event in Assistant().stream(
            message=PREAMBLE.format(name=bg.name) + bg.prompt,
            conversation_key=key,
            context={'user': owner, 'mcp_public': True, 'mode': ''},
        ):
            if event.get('type') in ('final', 'error') and event.get('result') is not None:
                text = event['result'].text or ''
                error = event['result'].error or ''
    except Exception as e:  # noqa: BLE001 — recorded on the row, never raised into Celery
        logger.warning('linda automation %s failed', bg.pk, exc_info=True)
        error = f'{type(e).__name__}: {e}'
    _record(bg, started, output=text, error=error)
    return 'failed' if error else 'completed'


def _record(bg, started, *, output: str = '', error: str = '') -> None:
    from plugins.installed.agent_core.models import BackgroundAgent

    with transaction.atomic():
        bg.last_run_at = started
        if output:
            bg.last_output = output[:20_000]
        bg.last_error = error[:5_000]
        bg.consecutive_failures = (bg.consecutive_failures or 0) + 1 if error else 0
        if error and bg.consecutive_failures >= max(1, int(bg.max_failures_before_pause)):
            bg.state = BackgroundAgent.STATE_PAUSED
        bg.save(
            update_fields=[
                'last_run_at',
                'last_output',
                'last_error',
                'consecutive_failures',
                'state',
                'updated_at',
            ]
        )
