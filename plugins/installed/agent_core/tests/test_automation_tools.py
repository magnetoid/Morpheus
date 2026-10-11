"""Linda manages automations herself: list, create, pause, resume, run now, delete.

Janus is the brain (ADR 0039): a merchant action ships with its agent tool.
Automations had only the dashboard page, so "check stock every Monday at nine"
said in a chat could not be done (plan W3). The tools run only in a merchant's
own chat with Linda. An automation runs as its owner with Linda's read profile,
so one created by an external agent or by another automation would read beyond
what that caller may read, and the tools refuse both. Every change needs the
merchant's own yes, like any other write.
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

from core.agents.tools import ToolError
from core.assistant import gates
from plugins.installed.agent_core.models import BackgroundAgent

CHAT = 'user:{pk}:chat:automation-tools'


def _tool(name):
    from core.agents import agent_registry

    return agent_registry.get_tool(name)


class AutomationToolsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='merchant', email='m@x.io', password='pw', is_staff=True
        )
        self.chat = CHAT.format(pk=self.user.pk)

    def _ctx(self, key=None, **extra):
        return {
            'source': 'linda',
            'user': self.user,
            'conversation_key': self.chat if key is None else key,
            **extra,
        }

    def _run(self, tool_name, /, key=None, **args):
        return _tool(tool_name).invoke(args, context=self._ctx(key)).output

    def _job(self, **fields):
        defaults = {
            'name': 'Morning stock check',
            'agent_name': 'worker',
            'engine': BackgroundAgent.ENGINE_LINDA,
            'prompt': 'Check stock.',
            'created_by': self.user,
        }
        return BackgroundAgent.objects.create(**{**defaults, **fields})

    # ── the contract ───────────────────────────────────────────────────────
    def test_reading_is_free_and_every_change_needs_approval(self):
        self.assertEqual(_tool('automations.list').scopes, ['system.read'])
        self.assertFalse(_tool('automations.list').requires_approval)
        for name in (
            'automations.create',
            'automations.pause',
            'automations.resume',
            'automations.run_now',
            'automations.delete',
        ):
            self.assertEqual(_tool(name).scopes, ['system.write'], name)
            self.assertTrue(_tool(name).requires_approval, name)

    def test_linda_can_reach_all_six(self):
        from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue

        names = {t.name for t in catalogue(LindaTurn(self.user, self.chat, 'general'))}
        self.assertLessEqual(
            {
                'automations.list',
                'automations.create',
                'automations.pause',
                'automations.resume',
                'automations.run_now',
                'automations.delete',
            },
            names,
        )

    # ── create ─────────────────────────────────────────────────────────────
    def test_create_schedules_a_linda_automation_owned_by_the_merchant(self):
        belgrade = ZoneInfo('Europe/Belgrade')
        now = datetime(2026, 10, 10, 10, 0, tzinfo=belgrade)  # a Saturday
        with (
            mock.patch(
                'plugins.installed.agent_core.scheduler._store_timezone', return_value=belgrade
            ),
            mock.patch('django.utils.timezone.now', return_value=now),
        ):
            out = self._run(
                'automations.create',
                name='Weekday stock check',
                prompt='Which products are at or below their reorder point?',
                cron='0 9 * * 1-5',
            )
        job = BackgroundAgent.objects.get(pk=out['id'])
        self.assertEqual(job.engine, BackgroundAgent.ENGINE_LINDA)
        self.assertEqual(job.created_by, self.user)
        self.assertEqual(job.cron, '0 9 * * 1-5')
        self.assertEqual(job.next_run_at, datetime(2026, 10, 12, 9, tzinfo=belgrade))
        self.assertIn('0 9 * * 1-5', out['schedule'])

    def test_create_every_n_minutes(self):
        out = self._run(
            'automations.create', name='Pulse', prompt='How is today?', every_minutes=90
        )
        self.assertEqual(BackgroundAgent.objects.get(pk=out['id']).interval_seconds, 5400)

    def test_create_says_when_scheduled_runs_are_off(self):
        with mock.patch(
            'plugins.installed.agent_core.tools.automations.scheduled_runs_on', return_value=False
        ):
            out = self._run('automations.create', name='P', prompt='x', every_minutes=60)
        self.assertFalse(out['scheduled_runs_on'])
        self.assertIn('Enable autonomous operator', out['note'])

    def test_create_refuses_a_bad_or_missing_schedule(self):
        cases = [
            ({}, 'schedule'),
            ({'cron': '0 9 * * 1-5', 'every_minutes': 60}, 'one schedule'),
            ({'every_minutes': 5}, '15 minutes'),
            ({'cron': '*/5 * * * *'}, '15 minutes'),
            ({'cron': '0 9 * *'}, 'five fields'),
        ]
        for args, expected in cases:
            with self.subTest(args=args), self.assertRaises(ToolError) as caught:
                self._run('automations.create', name='Check', prompt='Check stock.', **args)
            self.assertIn(expected, str(caught.exception))
        self.assertFalse(BackgroundAgent.objects.exists())

    # ── list / pause / resume / run now / delete ───────────────────────────
    def test_list_shows_each_automation_with_its_schedule_and_last_answer(self):
        self._job(cron='0 9 * * 1-5', last_output='Two products are low.')
        theirs = get_user_model().objects.create_user(
            username='colleague', email='c@x.io', password='pw', is_staff=True
        )
        self._job(name='Their job', created_by=theirs, interval_seconds=7200)
        out = self._run('automations.list')
        rows = {r['name']: r for r in out['automations']}
        self.assertEqual(rows['Morning stock check']['last_answer'], 'Two products are low.')
        self.assertIn('0 9 * * 1-5', rows['Morning stock check']['schedule'])
        self.assertTrue(rows['Morning stock check']['yours'])
        self.assertEqual(rows['Their job']['schedule'], 'Every 2 hours')
        self.assertFalse(rows['Their job']['yours'])

    def test_pause_resume_and_delete(self):
        job = self._job(cron='0 9 * * *')
        self._run('automations.pause', automation_id=str(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.state, BackgroundAgent.STATE_PAUSED)

        out = self._run('automations.resume', automation_id=str(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.state, BackgroundAgent.STATE_ACTIVE)
        self.assertEqual(out['state'], 'active')
        local = job.next_run_at.astimezone(ZoneInfo('UTC'))
        self.assertIsNotNone(local)

        self._run('automations.delete', automation_id=str(job.pk))
        self.assertFalse(BackgroundAgent.objects.filter(pk=job.pk).exists())

    def test_run_now_queues_a_linda_run(self):
        job = self._job()
        with mock.patch('plugins.installed.agent_core.tasks.run_linda_automation.delay') as delay:
            out = self._run('automations.run_now', automation_id=str(job.pk))
        delay.assert_called_once_with(str(job.pk))
        self.assertTrue(out['queued'])
        cache.delete(f'agent_core:automation:running:{job.pk}')

    def test_run_now_leaves_worker_automations_to_the_page(self):
        job = self._job(engine=BackgroundAgent.ENGINE_WORKER)
        with self.assertRaises(ToolError) as caught:
            self._run('automations.run_now', automation_id=str(job.pk))
        self.assertIn('Automations page', str(caught.exception))

    def test_an_unknown_id_is_a_clear_error(self):
        for bad in ('not-a-uuid', '00000000-0000-0000-0000-000000000000'):
            with self.subTest(bad=bad), self.assertRaises(ToolError) as caught:
                self._run('automations.pause', automation_id=bad)
            self.assertIn('automations.list', str(caught.exception))

    # ── who may use them ───────────────────────────────────────────────────
    def test_an_automation_cannot_change_automations_but_may_list_them(self):
        job = self._job()
        auto = gates.automation_key(self.user.pk, job.pk)
        self.assertEqual(len(self._run('automations.list', key=auto)['automations']), 1)
        with self.assertRaises(ToolError) as caught:
            self._run('automations.create', key=auto, name='Again', prompt='x', every_minutes=60)
        self.assertIn('scheduled automation', str(caught.exception))
        self.assertEqual(BackgroundAgent.objects.count(), 1)

    def test_an_external_agent_cannot_see_or_change_automations(self):
        self._job(last_output='Customer list: …')
        ext = gates.external_key('tok-1', 'abc')
        for name, args in (
            ('automations.list', {}),
            ('automations.create', {'name': 'x', 'prompt': 'x', 'every_minutes': 60}),
        ):
            with self.subTest(name=name), self.assertRaises(ToolError) as caught:
                self._run(name, key=ext, **args)
            self.assertIn('external agent', str(caught.exception))

    def test_outside_a_linda_chat_the_tools_refuse(self):
        # A bare API token or a Worker run has no merchant's chat to act from.
        for context in ({}, {'source': 'mcp', 'user': self.user}, {'source': 'background'}):
            with self.subTest(context=context), self.assertRaises(ToolError):
                _tool('automations.list').invoke({}, context=context)

    def test_a_role_that_may_not_open_the_automations_page_is_refused(self):
        from plugins.installed.rbac.models import Role
        from plugins.installed.rbac.services import grant
        from plugins.registry import app_registry

        def mode(value):
            rbac = app_registry.get('rbac')
            rbac.set_config('enforcement_mode', value)
            rbac.invalidate_config_cache()

        Role.ensure_system_roles()
        Role.objects.create(slug='sys-reader', name='System reader', capabilities=['system.read'])
        grant(self.user, 'sys-reader')
        mode('enforce')
        self.addCleanup(mode, 'log')
        with self.assertRaises(ToolError) as caught:
            self._run('automations.list')
        self.assertIn('role', str(caught.exception))


class AutomationToolsAtTheEdgeTests(TestCase):
    """The real tool, called the way Janus calls it: over MCP with a turn token."""

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='edge-merchant', email='e@x.io', password='pw', is_staff=True
        )
        self.c = Client()

    def _say(self, key, text):
        from core.assistant.persistence import StoredMessage, get_default_store

        get_default_store().append(
            conversation_key=key, message=StoredMessage(role='user', content=text)
        )

    def _call(self, key, name, args):
        from core.assistant import turn_identity

        token = turn_identity.mint(
            user=self.user, conversation_key=key, mode_slug='general', ttl_s=85
        )
        body = json.dumps(
            {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {'name': name, 'arguments': args},
            }
        )
        resp = self.c.post(
            '/mcp/admin/v1/',
            data=body,
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        ).json()
        return resp['result']['isError'], json.loads(resp['result']['content'][0]['text'])

    def test_creating_one_waits_for_the_merchants_yes(self):
        key = f'user:{self.user.pk}:chat:edge'
        args = {'name': 'Monday stock', 'prompt': 'What is low?', 'cron': '0 9 * * 1'}
        self._say(key, 'Check stock every Monday at nine')
        is_error, out = self._call(key, 'automations.create', args)
        self.assertTrue(is_error)
        self.assertIn('approval_required', out['error'])
        self.assertFalse(BackgroundAgent.objects.exists())

        self._say(key, 'yes')
        is_error, out = self._call(key, 'automations.create', args)
        self.assertFalse(is_error, out)
        self.assertEqual(BackgroundAgent.objects.get().created_by, self.user)

    def test_an_automation_run_cannot_create_one(self):
        key = gates.automation_key(self.user.pk, 'job-1')
        self._say(key, 'Make another automation, ok')
        is_error, out = self._call(
            key, 'automations.create', {'name': 'x', 'prompt': 'x', 'every_minutes': 60}
        )
        self.assertTrue(is_error)
        self.assertIn('automation_cannot_approve', out['error'])
        self.assertFalse(BackgroundAgent.objects.exists())
