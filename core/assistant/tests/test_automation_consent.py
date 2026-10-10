"""A scheduled automation can never approve a change to the store.

Automations run Linda with nobody watching. Consent is the merchant's own
next message, and an automation's prompt is stored in its conversation like a
message — so a prompt saying "…ok" on a five-minute schedule would land after
the previous run's proposal and approve it, unattended. The gate refuses
consent outright in an automation's conversation: Linda lists what she would
change, and the merchant asks for it in a chat.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

from django.core.cache import cache
from django.test import SimpleTestCase

from core.assistant import consent, gates

_TOOL = SimpleNamespace(scopes=[], requires_approval=True, supports_staging=False)
_ARGS = {'product_id': 'p1', 'price': '20.00'}


def _gate(key: str, message: str):
    return gates.gate_reason(
        tool=_TOOL,
        tool_name='products.update_price',
        args=_ARGS,
        scopes=['*'],
        context={},
        conversation_key=key,
        human_message=message,
        human_message_at=time.time() + 5,
        needs_consent=True,
    )


class AutomationConsentTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_an_automation_conversation_can_never_approve(self):
        key = gates.automation_key(7, 'job-1')
        consent.request(conversation_key=key, tool_name='products.update_price', args=_ARGS)
        reason = _gate(key, 'yes, go ahead')
        self.assertTrue(reason.startswith('automation_cannot_approve'), reason)
        self.assertTrue(gates.is_automation_key(key))

    def test_a_chat_still_asks_and_then_lets_the_yes_through(self):
        key = 'user:7:chat:abc'
        self.assertTrue(_gate(key, 'please change it').startswith('approval_required'))
        self.assertIsNone(_gate(key, 'yes'))
        self.assertFalse(gates.is_automation_key(key))
