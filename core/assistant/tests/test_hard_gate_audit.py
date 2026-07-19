"""Fix 21 — the destructive hard-gate writes a real audit row.

Regression: `_require_hard_gate` used to call
`AgentApprovalRequest.objects.create(agent_name=…, payload=…)` — fields that
don't exist on the model — so it raised on EVERY destructive op and the error
was swallowed. The audit row for the platform's MOST destructive actions was
never written (hunt #21). It now records an `agents.decision` row through
`core.audit.services.record_ai_decision`.
"""

from __future__ import annotations

from django.test import TestCase

from core.assistant.tools.ecommerce_writes import _require_hard_gate
from core.assistant.tools.filesystem import ToolError
from core.audit.models import AuditEvent


class HardGateAuditTests(TestCase):
    def _decisions(self):
        return AuditEvent.objects.filter(event_type='agents.decision')

    def test_success_writes_exactly_one_decision_row(self):
        self.assertEqual(self._decisions().count(), 0)  # nothing before

        _require_hard_gate(hard_gate_ack='YES', target_name='Widget', echo='widget')

        rows = self._decisions()
        self.assertEqual(rows.count(), 1)  # old code wrote ZERO
        row = rows.get()
        self.assertEqual(row.target, 'Widget')
        self.assertEqual(row.metadata.get('tool'), 'hard_gate.confirm')
        self.assertEqual(row.metadata.get('agent'), 'assistant')

    def test_bad_ack_raises_and_writes_no_row(self):
        with self.assertRaises(ToolError):
            _require_hard_gate(hard_gate_ack='NO', target_name='Widget', echo='widget')
        self.assertEqual(self._decisions().count(), 0)

    def test_echo_mismatch_raises_and_writes_no_row(self):
        with self.assertRaises(ToolError):
            _require_hard_gate(hard_gate_ack='YES', target_name='Widget', echo='wrong')
        self.assertEqual(self._decisions().count(), 0)
