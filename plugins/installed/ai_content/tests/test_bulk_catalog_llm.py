"""Bulk rewrite, translate and expand reach the model, under the guardrails.

They called ``complete(system=, messages=[...])`` on a core provider, which has only
``respond(messages=[LLMMessage])``, so every product failed with AttributeError,
and the call sat outside the kill switch and the spend cap besides. They now go
through the app's provider gateway, the one the dashboard's AI buttons use: it
obeys the guardrails and logs usage that counts toward the cap.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase

from plugins.installed.ai_assistant.services.llm import AIPaused
from plugins.installed.ai_content import services_bulk_catalog as bulk


class BulkCatalogModelCallTests(TestCase):
    def test_the_rewrite_comes_back_from_the_gateway(self):
        gateway = MagicMock()
        gateway.complete.return_value = '  A warmer description.  '
        with patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=gateway):
            text, _tokens = bulk._call_llm('Rewrite this')
        self.assertEqual(text, 'A warmer description.')
        self.assertEqual(gateway.complete.call_args.args[0], 'Rewrite this')

    def test_paused_ai_reaches_the_item_as_its_reason(self):
        gateway = MagicMock()
        gateway.complete.side_effect = AIPaused('AI is paused in Settings → Agent guardrails.')
        with (
            patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=gateway),
            self.assertRaises(AIPaused),
        ):
            bulk._call_llm('Rewrite this')
