"""The inbox lists conversations, under its mailbox tabs (v0.196.0).

The inbox listed every message, so a back-and-forth of five emails took five rows
and the reply sat apart from what it answered. Now each thread is one row: its
newest message, how many it holds, bold while any received one is unread. Opening
it reads the whole conversation, here and on the server.
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.utils import timezone

from plugins.installed.crm.models import MailAccount, MailMessage
from plugins.installed.crm.tests.test_inbox_reading import _InboxCase


class InboxThreadTests(_InboxCase):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.first = self.mail(
            subject='Kayak tour booking',
            thread_key='kayak',
            received_at=now - timedelta(hours=3),
            body_text='Is there room on Saturday?',
        )
        MailMessage.objects.create(
            account=self.account,
            direction='out',
            from_address='support@shop.test',
            to_addresses='guest@guest.test',
            subject='Re: Kayak tour booking',
            thread_key='kayak',
            sent_at=now - timedelta(hours=2),
            is_read=True,
        )
        self.last = self.mail(
            subject='Re: Kayak tour booking',
            thread_key='kayak',
            received_at=now - timedelta(hours=1),
            body_text='kayak-newest-line\n> Is there room on Saturday?',
            imap_uid=7,
            imap_folder='INBOX',
        )
        self.alone = self.mail(
            subject='Refund question', received_at=now - timedelta(hours=5), is_read=True
        )

    def _threads(self, path='/dashboard/crm/inbox/'):
        response = self.c.get(path)
        self.assertEqual(response.status_code, 200)
        return response, response.context['threads']

    def test_a_conversation_is_one_row(self):
        response, threads = self._threads()
        self.assertEqual([t['message'].pk for t in threads], [self.last.pk, self.alone.pk])
        kayak, refund = threads
        self.assertEqual(kayak['count'], 3)
        self.assertTrue(kayak['unread'])
        self.assertEqual(refund['count'], 1)
        self.assertFalse(refund['unread'])
        # The newest text, without the quoted message it answers.
        self.assertEqual(kayak['snippet'], 'kayak-newest-line')
        self.assertContains(response, f'/dashboard/crm/inbox/{self.last.pk}/')
        self.assertNotContains(response, f'/dashboard/crm/inbox/{self.first.pk}/')

    def test_the_tabs_sit_above_the_conversations(self):
        response, _ = self._threads()
        html = response.content.decode()
        self.assertLess(html.index('tab-list'), html.index('Re: Kayak tour booking'))

    def test_a_mailbox_tab_counts_its_own_conversations(self):
        sales = MailAccount.objects.create(
            label='Sales',
            email_address='sales@shop.test',
            imap_host='imap.shop.test',
            smtp_host='smtp.shop.test',
        )
        MailMessage.objects.create(
            account=sales, direction='in', from_address='b@b.test', subject='sales-only-marker'
        )
        response, threads = self._threads(f'/dashboard/crm/inbox/?account={sales.pk}')
        self.assertEqual([t['message'].subject for t in threads], ['sales-only-marker'])
        self.assertNotContains(response, 'Kayak tour booking')

    def test_a_search_lists_the_conversations_it_matches(self):
        _, threads = self._threads('/dashboard/crm/inbox/?q=room+on+Saturday')
        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0]['message'].thread_key, 'kayak')

    def test_opening_a_conversation_reads_all_of_it(self):
        with (
            mock.patch('plugins.installed.crm.views._queue_push_read') as push,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.c.get(f'/dashboard/crm/inbox/{self.last.pk}/')
        self.assertEqual(response.status_code, 200)
        self.first.refresh_from_db()
        self.last.refresh_from_db()
        self.assertTrue(self.first.is_read)
        self.assertTrue(self.last.is_read)
        # Only a message the server holds is pushed back as read.
        self.assertFalse(self.first.seen_pending)
        self.assertTrue(self.last.seen_pending)
        push.assert_called_once_with(self.last.pk)
        _, threads = self._threads()
        self.assertFalse(threads[0]['unread'])

    def test_opening_a_message_without_a_thread_reads_only_it(self):
        other = self.mail(subject='Another single one')
        response = self.c.get(f'/dashboard/crm/inbox/{other.pk}/')
        self.assertEqual(response.status_code, 200)
        other.refresh_from_db()
        self.last.refresh_from_db()
        self.assertTrue(other.is_read)
        self.assertFalse(self.last.is_read)
