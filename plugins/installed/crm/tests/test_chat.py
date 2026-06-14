"""Customer-support chat — public widget endpoints + CRM inbox + lead capture."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from plugins.installed.crm.models import ChatMessage, ChatThread, Lead
from plugins.installed.crm.plugin import CrmPlugin


class PublicChatTests(TestCase):
    def test_send_creates_thread_and_message(self):
        r = Client().post('/support/chat/send/', {'message': 'Do you ship to the EU?'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        tid = data['thread']
        self.assertTrue(ChatThread.objects.filter(id=tid).exists())
        self.assertEqual(ChatMessage.objects.filter(thread_id=tid, sender='customer').count(), 1)
        self.assertEqual(ChatThread.objects.get(id=tid).unread_staff, 1)

    def test_empty_message_rejected(self):
        r = Client().post('/support/chat/send/', {'message': '   '})
        self.assertEqual(r.status_code, 400)

    def test_followup_continues_same_thread(self):
        c = Client()
        t1 = c.post('/support/chat/send/', {'message': 'hi'}).json()['thread']
        t2 = c.post('/support/chat/send/', {'message': 'still there?', 'thread': t1}).json()[
            'thread'
        ]
        self.assertEqual(t1, t2)
        self.assertEqual(ChatMessage.objects.filter(thread_id=t1).count(), 2)

    def test_anon_email_captured_as_lead(self):
        r = Client().post(
            '/support/chat/send/', {'message': 'hello', 'email': 'shopper@example.test'}
        )
        thread = ChatThread.objects.get(id=r.json()['thread'])
        self.assertEqual(thread.email, 'shopper@example.test')
        self.assertIsNotNone(thread.lead_id)
        self.assertTrue(Lead.objects.filter(email='shopper@example.test').exists())

    def test_poll_returns_messages(self):
        c = Client()
        tid = c.post('/support/chat/send/', {'message': 'q1'}).json()['thread']
        msgs = c.get(f'/support/chat/poll/?thread={tid}').json()['messages']
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]['sender'], 'customer')


class CrmInboxTests(TestCase):
    def setUp(self):
        self.thread = ChatThread.objects.create(email='c@x.test', unread_staff=1)
        ChatMessage.objects.create(thread=self.thread, sender='customer', body='help')
        self.c = Client()
        self.c.force_login(
            get_user_model().objects.create_user(
                username='s', email='s@x.test', password='pw', is_staff=True
            )
        )

    def test_inbox_requires_staff(self):
        self.assertEqual(Client().get('/dashboard/crm/chat/').status_code, 302)

    def test_inbox_lists_threads(self):
        r = self.c.get('/dashboard/crm/chat/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'c@x.test')

    def test_opening_thread_clears_unread(self):
        r = self.c.get(f'/dashboard/crm/chat/{self.thread.id}/')
        self.assertEqual(r.status_code, 200)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.unread_staff, 0)

    def test_staff_reply_creates_message(self):
        self.c.post(
            f'/dashboard/crm/chat/{self.thread.id}/',
            {'action': 'reply', 'body': 'Yes, we ship to the EU!'},
        )
        self.assertTrue(ChatMessage.objects.filter(thread=self.thread, sender='staff').exists())

    def test_close_and_reopen(self):
        self.c.post(f'/dashboard/crm/chat/{self.thread.id}/', {'action': 'close'})
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, 'closed')


class PluginWiringTests(TestCase):
    def test_contributes_storefront_widget_and_dashboard_page(self):
        plugin = CrmPlugin()
        slots = {b.slot for b in plugin.contribute_storefront_blocks()}
        self.assertIn('global_below_body', slots)
        pages = {p.slug for p in plugin.contribute_dashboard_pages()}
        self.assertIn('chat', pages)


class PollRobustnessTests(TestCase):
    def test_poll_with_no_thread_does_not_500(self):
        r = Client().get('/support/chat/poll/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['messages'], [])

    def test_poll_with_garbage_thread_does_not_500(self):
        r = Client().get('/support/chat/poll/?thread=not-a-uuid')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['messages'], [])


class StaffNotifyTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(
            username='op', email='op@x.test', password='pw', is_staff=True
        )

    def test_first_unread_notifies_staff_once(self):
        from django.core import mail
        from django.test import override_settings

        from plugins.installed.crm.chat import post_customer_message

        thread = ChatThread.objects.create(email='c@x.test')
        with override_settings(DEFAULT_FROM_EMAIL='store@x.test'):
            post_customer_message(thread, 'first')
            self.assertEqual(len(mail.outbox), 1)  # one staff recipient
            self.assertEqual(mail.outbox[0].to, ['op@x.test'])
            # Still unread → no second notification on the next message.
            post_customer_message(thread, 'second')
            self.assertEqual(len(mail.outbox), 1)


class SupportAgentToolTests(TestCase):
    def test_threads_and_reply(self):
        from plugins.installed.crm.agent_tools import (
            crm_reply_support_tool,
            crm_support_threads_tool,
        )

        thread = ChatThread.objects.create(email='c@x.test', unread_staff=1)
        ChatMessage.objects.create(thread=thread, sender='customer', body='help')

        listed = crm_support_threads_tool.invoke({'status': 'open'}).output
        self.assertEqual(listed['count'], 1)
        self.assertEqual(listed['threads'][0]['unread'], 1)

        out = crm_reply_support_tool.invoke(
            {'thread_id': str(thread.id), 'message': 'On it!', 'close': True}
        ).output
        self.assertTrue(out['replied'])
        thread.refresh_from_db()
        self.assertEqual(thread.status, 'closed')
        self.assertTrue(
            ChatMessage.objects.filter(thread=thread, sender='staff').exists()
        )

    def test_reply_unknown_thread_errors(self):
        from plugins.installed.crm.agent_tools import crm_reply_support_tool

        out = crm_reply_support_tool.invoke({'thread_id': 'nope', 'message': 'x'}).output
        self.assertIn('error', out)
