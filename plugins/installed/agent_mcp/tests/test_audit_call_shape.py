"""The MCP audit row stores a failure the Activity page can read.

``_audit_call`` wrote ``output`` as a string — ``'error: …'`` on failure, a JSON
dump otherwise — while the Activity feed flags a call as failed only for a dict
carrying ``error`` (the Worker's shape). Every failed Linda/MCP call showed as a
green row and was missing from the "failed tool calls" count.
"""

from __future__ import annotations

from django.test import TestCase

from core.audit.models import AuditEvent
from plugins.installed.agent_mcp.views import _audit_call


class AuditCallShapeTests(TestCase):
    def test_failure_is_a_dict_with_error(self):
        _audit_call('catalog__update', {'slug': 'x'}, error='ValueError: boom')

        ev = AuditEvent.objects.get(event_type='agents.decision')
        self.assertEqual(ev.metadata['output'], {'error': 'ValueError: boom'})

    def test_small_success_output_is_kept_as_data(self):
        _audit_call('catalog__get', {'slug': 'x'}, output={'ok': True, 'count': 2})

        ev = AuditEvent.objects.get(event_type='agents.decision')
        self.assertEqual(ev.metadata['output'], {'ok': True, 'count': 2})

    def test_large_output_is_truncated_not_dropped(self):
        _audit_call('catalog__list', {}, output={'rows': ['x' * 50] * 100})

        ev = AuditEvent.objects.get(event_type='agents.decision')
        out = ev.metadata['output']
        self.assertIn('_truncated', out)
        self.assertLessEqual(len(out['_truncated']), 1000)
