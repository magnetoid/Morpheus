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
