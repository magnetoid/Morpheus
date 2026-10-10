"""A Linda automation never overlaps itself and never runs more often than
every fifteen minutes.

The minimum interval was 60 s and ``fire()`` queued a new Janus turn whether or
not the previous one was still running: a 60-second automation with 240-second
turns fills every worker slot (four by default) and shares one Janus session
with itself. The lock lives in the cache for as long as the task may run, so a
worker that dies mid-turn cannot wedge the automation.
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from plugins.installed.agent_core import scheduler
from plugins.installed.agent_core.models import BackgroundAgent


def _automation(**kw):
    owner = get_user_model().objects.create_user(
        username=f'o{BackgroundAgent.objects.count()}',
        email='o@x.test',
        password='pw',
        is_staff=True,
    )
    fields = dict(
        name='Stock check',
        agent_name='worker',
        engine=BackgroundAgent.ENGINE_LINDA,
        prompt='Check stock.',
        interval_seconds=60,
        created_by=owner,
    )
    fields.update(kw)
    return BackgroundAgent.objects.create(**fields)


class AutomationOverlapTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_running_automation_is_not_queued_again(self):
        bg = _automation()
        with mock.patch('plugins.installed.agent_core.tasks.run_linda_automation.delay') as delay:
            first = scheduler.fire(bg)
            second = scheduler.fire(bg)
        self.assertTrue(first['ok'])
        self.assertEqual(delay.call_count, 1)
        self.assertEqual(second, {'ok': False, 'error': 'already running'})

    def test_the_lock_is_released_when_the_run_ends(self):
        from plugins.installed.agent_core import linda_automations
        from plugins.installed.agent_core.tests.test_linda_automations import _FakeAssistant

        bg = _automation()
        with mock.patch('plugins.installed.agent_core.tasks.run_linda_automation.delay'):
            scheduler.fire(bg)
        self.assertTrue(scheduler.is_running(bg))

        with mock.patch.object(linda_automations, 'Assistant', _FakeAssistant):
            linda_automations.run_by_id(str(bg.pk))

        self.assertFalse(scheduler.is_running(bg))

    def test_the_lock_expires_with_the_task_time_limit(self):
        from plugins.installed.agent_core.tasks import run_linda_automation

        self.assertEqual(scheduler.RUN_LOCK_S, run_linda_automation.time_limit)


class LindaMinimumIntervalTests(TestCase):
    def test_a_linda_automation_waits_at_least_fifteen_minutes(self):
        bg = _automation(interval_seconds=60)
        before = timezone.now()
        scheduler.schedule_next(bg)
        self.assertEqual(scheduler.LINDA_MIN_INTERVAL_S, 900)
        self.assertGreaterEqual(bg.next_run_at, before + timedelta(seconds=899))

    def test_a_worker_automation_keeps_its_minute(self):
        bg = _automation(engine=BackgroundAgent.ENGINE_WORKER, interval_seconds=60)
        before = timezone.now()
        scheduler.schedule_next(bg)
        self.assertLess(bg.next_run_at, before + timedelta(seconds=120))

    def test_the_page_stores_the_minimum_for_linda(self):
        self.assertEqual(scheduler.min_interval_s(BackgroundAgent.ENGINE_LINDA), 900)
        self.assertEqual(scheduler.min_interval_s(BackgroundAgent.ENGINE_WORKER), 60)
