"""Changing an automation needs the same capability as seeing the list.

The Automations list (`background_agents_view`) required `system.write`, while
the endpoint behind its buttons — run now, pause, resume, delete — required
only `system.read`. So a role that may merely read system settings could start
an agent run or delete a scheduled job by POSTing to the URL directly.

Enforcement defaults to `log`, so these tests switch it to `enforce` and put it
back; without that, any capability string passes.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


def _set_mode(mode: str) -> None:
    from plugins.registry import app_registry

    plugin = app_registry.get('rbac')
    plugin.set_config('enforcement_mode', mode)
    plugin.invalidate_config_cache()


class AutomationActionAuthzTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.rbac.models import Role

        Role.ensure_system_roles()
        Role.objects.create(
            slug='system-reader', name='System reader', capabilities=['system.read']
        )
        users = get_user_model().objects
        cls.reader = users.create_user(
            username='sys_reader', email='reader@x.io', password='pw', is_staff=True
        )
        cls.admin = users.create_user(
            username='sys_admin', email='admin@x.io', password='pw', is_staff=True
        )

    def setUp(self):
        from plugins.installed.agent_core.models import BackgroundAgent
        from plugins.installed.rbac.services import grant

        grant(self.reader, 'system-reader')
        grant(self.admin, 'admin')
        _set_mode('enforce')
        self.addCleanup(_set_mode, 'log')
        self.job = BackgroundAgent.objects.create(name='Nightly check', prompt='Check stock.')

    def _post(self, user, action):
        self.client.force_login(user)
        return self.client.post(
            reverse(
                'agent_core_dash:background_action',
                kwargs={'bg_id': self.job.id, 'action': action},
            )
        )

    def test_a_read_only_role_cannot_delete_or_pause_an_automation(self):
        from plugins.installed.agent_core.models import BackgroundAgent

        for action in ('delete', 'pause'):
            with self.subTest(action=action):
                response = self._post(self.reader, action)
                self.assertNotEqual(response.status_code, 302, 'the action ran')
        job = BackgroundAgent.objects.get(pk=self.job.pk)
        self.assertNotEqual(job.state, BackgroundAgent.STATE_PAUSED)

    def test_a_role_that_can_change_the_system_can(self):
        from plugins.installed.agent_core.models import BackgroundAgent

        response = self._post(self.admin, 'pause')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            BackgroundAgent.objects.get(pk=self.job.pk).state, BackgroundAgent.STATE_PAUSED
        )
