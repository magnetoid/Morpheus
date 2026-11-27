"""Each mailbox is a tab at the top of the inbox (v0.194.0).

The inbox mixed every connected mailbox in one list, filtered by a dropdown.
Now "All" and each mailbox are tabs, each with its unread count; a tab keeps the
search and direction, and Compose from a mailbox's tab sends from it.
"""

from __future__ import annotations

from plugins.installed.crm.models import MailAccount, MailMessage
from plugins.installed.crm.tests.test_inbox_reading import _InboxCase


class InboxTabTests(_InboxCase):
    def setUp(self):
        super().setUp()
        self.sales = MailAccount.objects.create(
            label='Sales',
            email_address='sales@shop.test',
            imap_host='imap.shop.test',
            smtp_host='smtp.shop.test',
        )
        self.mail(subject='support-mail-marker')
        self.mail(subject='support-read-marker', is_read=True)
        MailMessage.objects.create(
            account=self.sales, direction='in', from_address='b@b.test', subject='sales-mail-marker'
        )

    def _tabs(self, path):
        response = self.c.get(path)
        self.assertEqual(response.status_code, 200)
        return response, {t['label']: t for t in response.context['mailbox_tabs']}

    def test_every_mailbox_is_a_tab_with_its_unread_count(self):
        response, tabs = self._tabs('/dashboard/crm/inbox/')
        self.assertEqual(list(tabs), ['All', 'Sales', 'Support'])
        self.assertEqual(tabs['All']['count'], 2)
        self.assertEqual(tabs['Support']['count'], 1)
        self.assertEqual(tabs['Sales']['count'], 1)
        self.assertTrue(tabs['All']['active'])
        self.assertContains(response, f'href="/dashboard/crm/inbox/?account={self.sales.pk}"')
        self.assertContains(response, 'support-mail-marker')
        self.assertContains(response, 'sales-mail-marker')

    def test_a_tab_shows_its_own_mailbox(self):
        response, tabs = self._tabs(f'/dashboard/crm/inbox/?account={self.sales.pk}')
        self.assertTrue(tabs['Sales']['active'])
        self.assertFalse(tabs['All']['active'])
        self.assertContains(response, 'sales-mail-marker')
        self.assertNotContains(response, 'support-mail-marker')
        self.assertContains(response, 'sales@shop.test')
        self.assertContains(response, f'/dashboard/crm/inbox/compose/?account={self.sales.pk}')

    def test_a_tab_keeps_the_search_and_direction(self):
        _, tabs = self._tabs('/dashboard/crm/inbox/?dir=in&q=order')
        self.assertEqual(
            tabs['Sales']['href'], f'/dashboard/crm/inbox/?account={self.sales.pk}&dir=in&q=order'
        )
        self.assertEqual(tabs['All']['href'], '/dashboard/crm/inbox/?dir=in&q=order')

    def test_an_unknown_mailbox_shows_them_all(self):
        for wanted in ('not-a-uuid', '00000000-0000-0000-0000-000000000000'):
            response, tabs = self._tabs(f'/dashboard/crm/inbox/?account={wanted}')
            self.assertTrue(tabs['All']['active'])
            self.assertContains(response, 'sales-mail-marker')

    def test_compose_from_a_tab_sends_from_that_mailbox(self):
        response = self.c.get(f'/dashboard/crm/inbox/compose/?account={self.sales.pk}')
        self.assertContains(response, f'<option value="{self.sales.pk}" selected>')

    def test_a_switched_off_mailbox_never_hands_compose_another_sender(self):
        MailAccount.objects.filter(pk=self.sales.pk).update(is_active=False)
        response = self.c.get(f'/dashboard/crm/inbox/?account={self.sales.pk}')
        self.assertNotContains(response, f'/dashboard/crm/inbox/compose/?account={self.sales.pk}')
        self.assertContains(response, 'disabled title="This mailbox is switched off')
        compose = self.c.get(f'/dashboard/crm/inbox/compose/?account={self.sales.pk}')
        self.assertContains(compose, '<option value="" disabled selected>Choose a mailbox</option>')
        self.assertNotContains(compose, ' selected>Support')
        posted = self.c.post(
            '/dashboard/crm/inbox/compose/',
            {'account': str(self.sales.pk), 'to': 'a@b.test', 'body': 'Hi'},
        )
        self.assertContains(posted, 'Pick an account')
