"""Background-agent scheduler.

Public surface:

    tick()     — run all due BackgroundAgents (called by Celery beat).
    fire(bg)   — run a single BackgroundAgent now (used by dashboard
                  "run now" button).
    schedule_next(bg) — compute and persist `next_run_at`.

Errors: a failed run is recorded on the BackgroundAgent row; after
`max_failures_before_pause` consecutive failures the agent is auto-paused
so a broken job doesn't burn through tokens.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.db import DatabaseError, transaction
from django.utils import timezone

logger = logging.getLogger('morpheus.agents.scheduler')

#: A Linda automation is a Janus turn of up to a few minutes on a worker with a
#: handful of slots; one that fires every minute fills them all and shares one
#: Janus session with itself. Fifteen minutes is the floor for that engine.
LINDA_MIN_INTERVAL_S = 900
#: How long the "running" lock lives — the Celery task's hard time limit, so a
#: worker that dies mid-turn frees the automation on its own.
RUN_LOCK_S = 420


def min_interval_s(engine: str) -> int:
    return LINDA_MIN_INTERVAL_S if engine == 'linda' else 60


def _running_key(bg) -> str:
    return f'agent_core:automation:running:{bg.pk}'


def mark_running(bg) -> bool:
    """Take the run lock. False when a run is already in flight."""
    from django.core.cache import cache

    return bool(cache.add(_running_key(bg), '1', timeout=RUN_LOCK_S))


def is_running(bg) -> bool:
    from django.core.cache import cache

    return cache.get(_running_key(bg)) is not None


def clear_running(bg) -> None:
    from django.core.cache import cache

    cache.delete(_running_key(bg))


def _store_timezone():
    """The merchant's time zone (Settings → General), else the project's."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from django.conf import settings

    try:
        from core.models import StoreSettings

        return ZoneInfo(str(StoreSettings.get('timezone') or settings.TIME_ZONE))
    except (ZoneInfoNotFoundError, ValueError, DatabaseError):
        return ZoneInfo(settings.TIME_ZONE)


def next_daily(at, now=None):
    """The next time the store's clock reads `at` (a `datetime.time`)."""
    local = (now or timezone.now()).astimezone(_store_timezone())
    candidate = local.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    return candidate if candidate > local else candidate + timedelta(days=1)


def schedule_next(bg) -> None:
    if getattr(bg, 'daily_at', None):
        bg.next_run_at = next_daily(bg.daily_at)
    else:
        floor = min_interval_s(getattr(bg, 'engine', ''))
        bg.next_run_at = timezone.now() + timedelta(seconds=max(floor, int(bg.interval_seconds)))
    bg.save(update_fields=['next_run_at', 'updated_at'])


def fire(bg) -> dict[str, Any]:
    """Run one BackgroundAgent now. Returns a small status dict.

    A Linda automation is queued as its own task (a Janus turn takes minutes and
    must not hold up the tick or a "Run now" click); see linda_automations.py.
    """
    from plugins.installed.agent_core.models import BackgroundAgent
    from plugins.installed.agent_core.services import run_agent

    if getattr(bg, 'engine', '') == BackgroundAgent.ENGINE_LINDA:
        from plugins.installed.agent_core.tasks import run_linda_automation

        # One turn at a time per automation; linda_automations.run() releases
        # the lock, and it expires with the task's time limit either way.
        if not mark_running(bg):
            return {'ok': False, 'error': 'already running'}
        run_linda_automation.delay(str(bg.pk))
        return {'ok': True, 'queued': True}

    started = timezone.now()
    try:
        result = run_agent(
            agent_name=bg.agent_name,
            user_message=bg.prompt,
            context={
                'source': 'background',
                'background_agent_id': str(bg.id),
                **(bg.context_overrides or {}),
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('background_agent: fire failed for %s: %s', bg.id, e)
        try:
            with transaction.atomic():
                bg.consecutive_failures = (bg.consecutive_failures or 0) + 1
                bg.last_error = f'{type(e).__name__}: {e}'[:5_000]
                bg.last_run_at = started
                if bg.consecutive_failures >= max(1, int(bg.max_failures_before_pause)):
                    bg.state = BackgroundAgent.STATE_PAUSED
                    logger.warning(
                        'background_agent: %s auto-paused after %d failures',
                        bg.id,
                        bg.consecutive_failures,
                    )
                schedule_next(bg)
        except DatabaseError:
            pass
        return {'ok': False, 'error': str(e)}

    try:
        with transaction.atomic():
            bg.last_run_at = started
            bg.last_run_id = getattr(getattr(result, 'trace', None), 'run_id', '') or ''
            bg.last_error = (result.error or '')[:5_000]
            bg.consecutive_failures = (
                0 if result.state == 'completed' else (bg.consecutive_failures or 0) + 1
            )
            schedule_next(bg)
    except DatabaseError:
        pass
    return {
        'ok': True,
        'state': result.state,
        'tokens': result.trace.prompt_tokens + result.trace.completion_tokens,
    }


def tick() -> int:
    """Run every active BackgroundAgent whose next_run_at <= now.

    Returns the number of agents fired. Designed to be called every minute.

    Proactive runs are gated by the AUTONOMY_ENABLED filter — autonomy is
    opt-in (fail-safe off when no subscriber enables it). Manual "run now"
    (`fire`) is unaffected.
    """
    from core.agents.events import AgentEvents
    from morpheus.core import hook_registry

    if not hook_registry.filter(AgentEvents.AUTONOMY_ENABLED, value=False):
        logger.debug('background_agent: tick skipped — autonomy disabled')
        return 0

    from plugins.installed.agent_core.models import BackgroundAgent

    now = timezone.now()
    fired = 0
    try:
        due = list(
            BackgroundAgent.objects.filter(state=BackgroundAgent.STATE_ACTIVE)
            .filter(next_run_at__isnull=False, next_run_at__lte=now)
            .order_by('next_run_at')[:25]
        )
    except DatabaseError as e:
        logger.warning('background_agent: tick query failed: %s', e)
        return 0

    for bg in due:
        # Reschedule first so two beats firing on top of each other don't double-run.
        schedule_next(bg)
        try:
            fire(bg)
            fired += 1
        except Exception as e:  # noqa: BLE001
            logger.error(
                'background_agent: unexpected tick failure for %s: %s', bg.id, e, exc_info=True
            )
    return fired
