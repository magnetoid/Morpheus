"""Linda keeps every chat, and you can go back to one and continue it.

Owner's ask (2026-10-10): "Linda should remember old chats so we can continue
them — in a tab of her menu." Each chat is its own conversation (its own key,
so its own Janus session and its own consent context), owned by one staff user
and checked on the server for every read and write. The floating widget keeps
its one running thread (the legacy ``user:<pk>`` key), which is listed too.
"""

from __future__ import annotations

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.assistant.models import AssistantConversation, AssistantMessage


class _FakeAssistant:
    """Stands in for the engine: records the key it was given, answers once."""

    keys: list[str] = []
    contexts: list[dict] = []

    def stream(self, *, message, conversation_key, context):
        type(self).keys.append(conversation_key)
        type(self).contexts.append(context)
        yield {'type': 'assistant_text', 'text': 'ok'}


def _events(response) -> list[dict]:
    body = b''.join(response.streaming_content).decode()
    return [json.loads(line[6:]) for line in body.split('\n') if line.startswith('data: ')]


class ChatsTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(
            username='owner', email='owner@x.io', password='pw', is_staff=True
        )
        self.other = users.create_user(
            username='other', email='other@x.io', password='pw', is_staff=True
        )
        _FakeAssistant.keys = []
        patcher = mock.patch('core.assistant.views.Assistant', _FakeAssistant)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.force_login(self.owner)

    def _say(self, message, conversation=None):
        body = {'message': message}
        if conversation is not None:
            body['conversation'] = conversation
        return self.client.post(
            '/dashboard/assistant/stream/', data=json.dumps(body), content_type='application/json'
        )

    def _chat(self, user, title='Old chat'):
        conv = AssistantConversation.objects.create(
            key=f'user:{user.pk}:chat:{user.pk}abc', user=user, title=title
        )
        AssistantMessage.objects.create(conversation=conv, role='user', content='How are sales?')
        AssistantMessage.objects.create(conversation=conv, role='assistant', content='Up 12%.')
        return conv

    def test_the_first_message_starts_a_chat_owned_by_you_and_titled_by_it(self):
        events = _events(self._say('Which products sold best this week?', conversation=''))
        self.assertEqual(events[0]['type'], 'conversation')
        conv = AssistantConversation.objects.get(pk=events[0]['id'])
        self.assertEqual(conv.user, self.owner)
        self.assertEqual(conv.title, 'Which products sold best this week?')
        self.assertEqual(_FakeAssistant.keys, [conv.key])

    def test_a_chat_continues_in_its_own_conversation(self):
        conv = self._chat(self.owner)
        events = _events(self._say('And last week?', conversation=str(conv.pk)))
        self.assertNotIn('conversation', [e['type'] for e in events])
        self.assertEqual(_FakeAssistant.keys, [conv.key])

    def test_someone_elses_chat_cannot_be_continued(self):
        theirs = self._chat(self.other)
        self.assertEqual(self._say('Hi', conversation=str(theirs.pk)).status_code, 404)
        self.assertEqual(_FakeAssistant.keys, [])

    def test_the_widget_keeps_its_one_running_thread(self):
        _events(self._say('Hello from the widget'))
        self.assertEqual(_FakeAssistant.keys, [f'user:{self.owner.pk}'])
        thread = AssistantConversation.objects.get(key=f'user:{self.owner.pk}')
        self.assertEqual(thread.user, self.owner)

    def test_opening_a_chat_shows_its_messages(self):
        conv = self._chat(self.owner)
        html = self.client.get(f'/dashboard/assistant/?c={conv.pk}').content.decode()
        self.assertIn('How are sales?', html)
        self.assertIn('Up 12%.', html)
        self.assertIn(str(conv.pk), html)

    def test_someone_elses_chat_cannot_be_opened(self):
        theirs = self._chat(self.other)
        self.assertEqual(self.client.get(f'/dashboard/assistant/?c={theirs.pk}').status_code, 404)
        resp = self.client.get(f'/dashboard/assistant/history/?conversation={theirs.pk}')
        self.assertEqual(resp.status_code, 404)

    def test_the_chats_tab_lists_only_your_chats(self):
        mine = self._chat(self.owner, title='Weekly sales')
        self._chat(self.other, title='Their secret plans')
        html = self.client.get('/dashboard/assistant/chats/').content.decode()
        self.assertIn('Weekly sales', html)
        self.assertIn(f'/dashboard/assistant/?c={mine.pk}', html)
        self.assertNotIn('Their secret plans', html)

    def test_a_chat_can_be_renamed_and_archived_by_its_owner_only(self):
        mine = self._chat(self.owner)
        theirs = self._chat(self.other)
        base = '/dashboard/assistant/chats/'
        self.client.post(f'{base}{mine.pk}/rename/', {'title': 'Renamed'})
        self.client.post(f'{base}{mine.pk}/archive/')
        mine.refresh_from_db()
        self.assertEqual(mine.title, 'Renamed')
        self.assertTrue(mine.archived)
        self.assertNotIn('Renamed', self.client.get(base).content.decode())
        self.assertIn('Renamed', self.client.get(f'{base}?archived=1').content.decode())

        self.assertEqual(self.client.post(f'{base}{theirs.pk}/archive/').status_code, 404)
        theirs.refresh_from_db()
        self.assertFalse(theirs.archived)

    def test_chats_is_a_tab_of_lindas_section(self):
        html = self.client.get('/dashboard/assistant/chats/').content.decode()
        self.assertIn('href="/dashboard/assistant/chats/"', html)


class ModelPickerTests(TestCase):
    """A model can be picked for the next message (owner's ask, 2026-10-10)."""

    _MODELS = [
        {'name': 'grok', 'model': 'grok-4', 'label': 'Grok · grok-4'},
        {'name': 'deepseek', 'model': 'deepseek-chat', 'label': 'DeepSeek · deepseek-chat'},
    ]

    def setUp(self):
        user = get_user_model().objects.create_user(
            username='picker', email='picker@x.io', password='pw', is_staff=True
        )
        self.client.force_login(user)
        _FakeAssistant.keys, _FakeAssistant.contexts = [], []
        for target, value in (
            ('core.assistant.views.Assistant', _FakeAssistant),
            ('core.assistant.janus_engine.selectable_providers', lambda: self._MODELS),
        ):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_composer_offers_the_models_with_a_key(self):
        html = self.client.get('/dashboard/assistant/').content.decode()
        self.assertIn('<select name="provider"', html)
        self.assertIn('<option value="deepseek">DeepSeek · deepseek-chat</option>', html)

    def test_the_pick_rides_on_the_message(self):
        body = {'message': 'Hi', 'conversation': '', 'provider': 'deepseek'}
        response = self.client.post(
            '/dashboard/assistant/stream/', data=json.dumps(body), content_type='application/json'
        )
        _events(response)
        self.assertEqual(_FakeAssistant.contexts[0]['provider'], 'deepseek')

    def test_one_model_needs_no_picker(self):
        with mock.patch(
            'core.assistant.janus_engine.selectable_providers', lambda: self._MODELS[:1]
        ):
            html = self.client.get('/dashboard/assistant/').content.decode()
        self.assertNotIn('<select name="provider"', html)
