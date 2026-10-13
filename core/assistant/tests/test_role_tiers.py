"""Janus does for a staff member what their role lets them do on the dashboard.

A shop manager's Janus once held the whole store profile — apps on and off, platform
settings, updates — whatever their role allowed them to do themselves. Now the profile
is narrowed by the same capabilities the dashboard checks (core/authz.py), while the
store enforces roles. Superusers keep everything; the tier is the person's, never a
token's (docs/plans/janus-core-brain-2026-10.md, B).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.assistant.gates import CAPABILITY_FOR_SCOPE, LINDA_SCOPES, person_scopes


def _set_mode(mode: str) -> None:
    from plugins.registry import app_registry

    plugin = app_registry.get('rbac')
    plugin.set_config('enforcement_mode', mode)
    plugin.invalidate_config_cache()


class RoleTierTests(TestCase):
    def setUp(self):
        from plugins.installed.rbac.models import Role

        Role.ensure_system_roles()
        User = get_user_model()
        self.manager = User.objects.create_user('stock', 'stock@example.com', 'x', is_staff=True)
        self.owner = User.objects.create_superuser('boss', 'boss@example.com', 'x')
        self.addCleanup(_set_mode, 'log')

    def _grant(self, user, role):
        from plugins.installed.rbac.services import grant

        grant(user, role)

    def _names(self, user):
        from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue

        turn = LindaTurn(user=user, conversation_key=f'user:{user.pk}:chat:a', mode_slug='general')
        return {t.name for t in catalogue(turn)}

    def test_log_only_changes_nothing(self):
        _set_mode('log')
        self.assertEqual(person_scopes(self.manager), LINDA_SCOPES)

    def test_an_inventory_manager_gets_stock_work_not_the_platform(self):
        _set_mode('enforce')
        self._grant(self.manager, 'inventory_manager')
        names = self._names(self.manager)
        self.assertIn('inventory.adjust_stock', names)
        for platform in ('plugins.toggle', 'settings.set', 'updates.apply', 'orders.refund'):
            self.assertNotIn(platform, names)

    def test_the_edge_refuses_what_the_role_does_not_grant(self):
        from core.assistant import gates
        from core.assistant.tools.admin_ops import settings_set_tool
        from plugins.installed.agent_mcp.linda_turn import LindaTurn, scope_profile

        _set_mode('enforce')
        self._grant(self.manager, 'inventory_manager')
        turn = LindaTurn(user=self.manager, conversation_key='user:1:chat:a', mode_slug='general')
        reason = gates.gate_reason(
            tool=settings_set_tool,
            tool_name='settings.set',
            args={},
            scopes=scope_profile(turn),
            context={'user': self.manager},
            conversation_key=turn.conversation_key,
            human_message='yes',
        )
        self.assertIn('Missing required scopes', reason or '')

    def test_a_superuser_keeps_everything(self):
        _set_mode('enforce')
        self.assertEqual(person_scopes(self.owner), LINDA_SCOPES)

    def test_the_admin_role_holds_every_capability_janus_asks_for(self):
        # A capability no role can hold would take that work from every staff
        # member's Janus the day the store enforces roles.
        from plugins.installed.rbac.models import _DEFAULT_TEMPLATES

        admin = set(_DEFAULT_TEMPLATES['admin'])
        missing = {s for s in LINDA_SCOPES if CAPABILITY_FOR_SCOPE.get(s, s) not in admin}
        self.assertEqual(missing, set())
