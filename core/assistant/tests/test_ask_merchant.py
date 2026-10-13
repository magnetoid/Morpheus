"""Linda can ask the merchant a question with buttons, and a button never approves.

In Janus's Telegram gateway the agent asks a question mid-task and offers
choices; the dashboard chat had no such turn. ``assistant.ask`` puts the question
and up to four choices on the merchant's screen, and the chat sends a click as
the merchant's next message, marked as an answer. The choices are the model's
words, so an answer must never spend consent for a write: only a typed message,
or the Approve card that shows the exact refused call, can do that.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.agents.tools import ToolError
from core.assistant import consent, gates
from core.assistant.models import AssistantConversation, AssistantMessage


def _ask_tool():
    from core.assistant.tools import get_default_tools

    return next(t for t in get_default_tools() if t.name == 'assistant.ask')


class AskToolTests(TestCase):
    def test_it_is_a_read_tool_every_mode_can_reach(self):
        tool = _ask_tool()
        self.assertEqual(list(tool.scopes), ['system.read'])
        self.assertFalse(gates.is_write_tool(tool))

    def test_it_returns_the_question_and_up_to_four_clean_choices(self):
        out = (
            _ask_tool()
            .invoke(
                {
                    'question': 'Which collection should get the discount?',
                    'choices': ['Summer', ' Summer ', '', 'Winter', 'Sale', 'New in', 'Gifts'],
                }
            )
            .output
        )
        self.assertEqual(out['kind'], 'question')
        self.assertEqual(out['question'], 'Which collection should get the discount?')
        self.assertEqual(out['choices'], ['Summer', 'Winter', 'Sale', 'New in'])
        self.assertIn('end your turn', out['note'])

    def test_a_question_is_required(self):
        with self.assertRaises(ToolError):
            _ask_tool().invoke({'question': '  '})


class AnswerIsNotConsentTests(TestCase):
    CONV = 'user:1:chat:ask'

    def setUp(self):
        self.conv = AssistantConversation.objects.create(key=self.CONV)
        self.addCleanup(
            consent.clear, conversation_key=self.CONV, tool_name='t.write', args={'x': 1}
        )

    def _proposal_then(self, **message):
        consent.request(conversation_key=self.CONV, tool_name='t.write', args={'x': 1})
        later = datetime.now(UTC) + timedelta(seconds=2)
        row = AssistantMessage.objects.create(conversation=self.conv, role='user', **message)
        AssistantMessage.objects.filter(pk=row.pk).update(created_at=later)

    def _spends(self) -> bool:
        text, at = gates.latest_human_turn(self.CONV)
        return consent.consume(
            conversation_key=self.CONV,
            tool_name='t.write',
            args={'x': 1},
            human_message=text,
            human_message_at=at,
        )

    def test_a_clicked_answer_never_approves_a_write(self):
        self._proposal_then(content='Yes', tool_name='answer')
        self.assertFalse(self._spends())

    def test_a_typed_yes_still_does(self):
        self._proposal_then(content='Yes')
        self.assertTrue(self._spends())


class AnswerFlagTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='m', email='m@x.io', password='pw', is_staff=True
        )
        self.client.force_login(self.user)
        patcher = mock.patch('core.assistant.janus_settings.engine_enabled', return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, **body):
        resp = self.client.post(
            '/dashboard/assistant/stream/',
            data=json.dumps({'message': 'Summer', 'conversation': '', **body}),
            content_type='application/json',
        )
        b''.join(resp.streaming_content)

    def test_a_button_answer_is_stored_marked(self):
        self._post(answer=True)
        msg = AssistantMessage.objects.get(role='user')
        self.assertEqual((msg.content, msg.tool_name), ('Summer', 'answer'))

    def test_a_typed_message_is_not(self):
        self._post()
        self.assertEqual(AssistantMessage.objects.get(role='user').tool_name, '')


class CardWordsTests(TestCase):
    """The chat's Approve and Decline send fixed words the consent kernel reads."""

    def test_approve_reads_as_yes_and_decline_as_no(self):
        from pathlib import Path

        js = (
            Path(__file__).resolve().parents[1] / 'static' / 'assistant' / 'activity.js'
        ).read_text(encoding='utf-8')
        self.assertIn("reply('Yes, go ahead.', {})", js)
        self.assertIn('reply("No, don\'t make that change.", {})', js)
        self.assertIn('reply(c, {answer: true})', js)
        self.assertTrue(consent.is_affirmative('Yes, go ahead.'))
        self.assertFalse(consent.is_affirmative("No, don't make that change."))

    def test_both_chats_send_the_answer_mark(self):
        from pathlib import Path

        templates = Path(__file__).resolve().parents[1] / 'templates' / 'assistant'
        for name in ('page.html', '_floating_widget.html'):
            source = (templates / name).read_text(encoding='utf-8')
            self.assertIn('answer: isAnswer', source, name)
            self.assertIn('reply: reply', source, name)
