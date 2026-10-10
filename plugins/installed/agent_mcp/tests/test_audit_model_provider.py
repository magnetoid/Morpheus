"""A Linda tool call's decision row names the model and provider behind it.

``_audit_call`` passed neither, so ``decisions_by_model`` in the AI-Act export
was ``{}`` on every store (0 of 4,938 rows on dotbooks carried a model). The
turn token now carries both and the MCP edge copies them onto the row.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.audit.models import AuditEvent
from plugins.installed.agent_mcp import views
from plugins.installed.agent_mcp.linda_turn import LindaTurn


class AuditCallProvenanceTests(TestCase):
    def test_the_turns_model_and_provider_land_on_the_decision(self):
        user = get_user_model().objects.create_user(
            username='prov', email='prov@x.test', password='pw', is_staff=True
        )
        views._request_state.linda_turn = LindaTurn(
            user=user,
            conversation_key='user:1',
            mode_slug='',
            provider='deepseek',
            model='deepseek-chat',
        )
        try:
            views._audit_call('catalog__get', {'slug': 'x'}, output={'ok': True})
        finally:
            views._request_state.linda_turn = None

        ev = AuditEvent.objects.get(event_type='agents.decision')
        self.assertEqual(ev.metadata.get('model'), 'deepseek-chat')
        self.assertEqual(ev.metadata.get('provider'), 'deepseek')

    def test_without_a_turn_the_row_is_still_written(self):
        views._request_state.linda_turn = None
        views._audit_call('catalog__get', {'slug': 'x'}, output={'ok': True})
        self.assertEqual(AuditEvent.objects.filter(event_type='agents.decision').count(), 1)
