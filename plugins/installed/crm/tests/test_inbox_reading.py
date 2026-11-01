"""The CRM inbox: no toast per email, readable and safe mail, replies that reach the other side."""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import Client, SimpleTestCase, TestCase
from django.utils import timezone

from plugins.installed.crm.inbox import fetch_account
from plugins.installed.crm.mail_render import header_text, render_body
from plugins.installed.crm.models import ChatMessage, ChatThread, CrmTask, MailAccount, MailMessage

ENCODED = '=?UTF-8?Q?Potvrda_rezervacije_=C4=8C=C4=86?='

HTML = """<html><head><style>.promo{color:red}</style><title>Hidden title</title></head><body>
<!--[if mso]><p>outlook-only</p><![endif]-->
<span style="display:none">preheader-marker</span>
<table width="600" style="width:600px"><tr><td>
<img src="https://tracker.example.test/pixel.gif" width="1" height="1">
<p>Booking <b>#12345</b> confirmed. <a href="https://example.test/b/12345" onclick="x()">Open booking</a></p>
<script>alert('mail-script')</script>
<a href="javascript:alert(2)">bad-link</a>
</td></tr></table>
<div class="gmail_quote">On Monday the shop wrote:<blockquote>older-quoted-marker</blockquote></div>
</body></html>"""

TEXT = (
    'Hi,\r\n\r\nThanks for the order.\r\nTracking link: https://example.com/t/123\r\n\r\n'
    'Best,\r\nAna\r\n\r\nOn Mon, Oct 27, 2026 at 10:00 Shop <shop@example.test> wrote:\r\n'
    '> text-quoted-marker\r\n> second line\r\n'
)


class _Message:
    def __init__(self, body_text='', body_html=''):
        self.body_text, self.body_html = body_text, body_html


class MailRenderTests(SimpleTestCase):
    def test_header_text_decodes_encoded_words_and_keeps_plain_text(self):
        self.assertEqual(header_text(ENCODED), 'Potvrda rezervacije ČĆ')
        self.assertEqual(header_text('Order 12'), 'Order 12')
        self.assertEqual(header_text(None), '')
        self.assertEqual(header_text('=?x-unknown?Q?abc?='), '=?x-unknown?Q?abc?=')

    def test_html_mail_loses_everything_but_its_text_and_links(self):
        out = str(render_body(_Message(body_html=HTML)))
        self.assertIn('class="crm-mail-body crm-mail-html"', out)
        self.assertIn('<b>#12345</b>', out)
        for gone in (
            '.promo',
            'Hidden title',
            'outlook-only',
            'preheader-marker',
            'tracker.example.test',
            'mail-script',
            'javascript:',
            'onclick',
            'style=',
            'width=',
            '<img',
        ):
            self.assertNotIn(gone, out)
        self.assertIn('href="https://example.test/b/12345"', out)
        self.assertIn('rel="nofollow noopener noreferrer"', out)
        self.assertIn('Images in this email are not shown.', out)

    def test_html_quote_folds_under_details(self):
        out = str(render_body(_Message(body_html=HTML)))
        main, _, quoted = out.partition('<details class="crm-mail-quote">')
        self.assertIn('#12345', main)
        self.assertNotIn('older-quoted-marker', main)
        self.assertIn('older-quoted-marker', quoted)

    def test_text_mail_keeps_lines_links_and_folds_the_quote(self):
        out = str(render_body(_Message(body_text=TEXT, body_html='')))
        self.assertIn('class="crm-mail-body crm-mail-text"', out)
        main, _, quoted = out.partition('<details class="crm-mail-quote">')
        self.assertIn('Thanks for the order.\nTracking link:', main)
        self.assertNotIn('\r', out)
        self.assertIn('href="https://example.com/t/123"', main)
        self.assertNotIn('text-quoted-marker', main)
        self.assertIn('&gt; text-quoted-marker', quoted)
        self.assertNotIn('Images in this email', out)

    def test_text_mail_is_escaped(self):
        out = str(render_body(_Message(body_text='<b onmouseover="x()">hi</b>')))
        self.assertNotIn('<b onmouseover', out)
        self.assertIn('&lt;b', out)

    def test_a_mail_that_is_only_a_quote_is_not_folded_away(self):
        out = str(render_body(_Message(body_text='> only-quote-marker\n> more')))
        self.assertNotIn('<details', out)
        self.assertIn('only-quote-marker', out)

    def test_changed_templates_compile(self):
        for name in (
            'crm/inbox.html',
            'crm/inbox_message.html',
            'crm/chat/thread.html',
            'admin_dashboard/base.html',
        ):
            get_template(name)


class _InboxCase(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='staff', email='staff@shop.test', password='pw', is_staff=True
        )
        self.c = Client()
        self.c.force_login(self.staff)
        self.account = MailAccount.objects.create(
            label='Support',
            email_address='support@shop.test',
            imap_host='imap.shop.test',
            smtp_host='smtp.shop.test',
        )

    def mail(self, **kw):
        kw.setdefault('direction', 'in')
        kw.setdefault('from_address', 'guest@guest.test')
        kw.setdefault('received_at', timezone.now())
        return MailMessage.objects.create(account=self.account, **kw)


class InboxListTests(_InboxCase):
    def test_emails_are_not_turned_into_toasts(self):
        for n in range(3):
            self.mail(subject=f'inbox-row-{n}')
        r = self.c.get('/dashboard/crm/inbox/')
        self.assertEqual(r.status_code, 200)
        for n in range(3):
            self.assertContains(r, f'inbox-row-{n}')
        self.assertNotContains(r, '_toastQueue.push')

    def test_encoded_subject_reads_decoded(self):
        self.mail(subject=ENCODED)
        r = self.c.get('/dashboard/crm/inbox/')
        self.assertContains(r, 'Potvrda rezervacije ČĆ')
        self.assertNotContains(r, '=?UTF-8?Q?')

    def test_newest_mail_first_whichever_way_it_went(self):
        now = timezone.now()
        self.mail(subject='older-received', received_at=now - timedelta(days=2))
        MailMessage.objects.create(
            account=self.account,
            direction='out',
            from_address='support@shop.test',
            to_addresses='guest@guest.test',
            subject='middle-sent',
            sent_at=now - timedelta(days=1),
        )
        self.mail(subject='newest-received', received_at=now)
        body = self.c.get('/dashboard/crm/inbox/').content.decode()
        self.assertLess(body.index('newest-received'), body.index('middle-sent'))
        self.assertLess(body.index('middle-sent'), body.index('older-received'))

    def test_sync_reports_what_it_fetched(self):
        with mock.patch('plugins.installed.crm.inbox.fetch_all_active', return_value={'S': 2}):
            r = self.c.post('/dashboard/crm/inbox/', {'action': 'sync'}, follow=True)
        self.assertContains(r, '2 new message(s).')

    def test_sync_reports_a_mailbox_it_could_not_reach(self):
        MailAccount.objects.filter(pk=self.account.pk).update(last_error='connect: refused')
        with mock.patch('plugins.installed.crm.inbox.fetch_all_active', return_value={'S': 0}):
            r = self.c.post('/dashboard/crm/inbox/', {'action': 'sync'}, follow=True)
        self.assertContains(r, 'Could not check Support.')


class InboxMessageTests(_InboxCase):
    def test_html_mail_renders_sanitised(self):
        m = self.mail(subject='html-mail', body_html=HTML)
        r = self.c.get(f'/dashboard/crm/inbox/{m.pk}/')
        self.assertContains(r, 'class="crm-mail-body crm-mail-html"')
        self.assertNotContains(r, 'tracker.example.test')
        self.assertNotContains(r, 'mail-script')
        self.assertNotContains(r, '.promo{')

    def test_reply_to_a_sent_mail_goes_to_its_recipient(self):
        sent = MailMessage.objects.create(
            account=self.account,
            direction='out',
            from_address='support@shop.test',
            to_addresses='buyer@guest.test',
            subject='Re: Order 7',
            sent_at=timezone.now(),
        )
        r = self.c.get(f'/dashboard/crm/inbox/{sent.pk}/')
        self.assertContains(r, 'name="to" value="buyer@guest.test"')
        self.assertContains(r, 'name="subject" value="Re: Order 7"')
        self.assertNotContains(r, 'Re: Re:')

    def test_reply_subject_is_the_decoded_subject(self):
        m = self.mail(subject=ENCODED)
        r = self.c.get(f'/dashboard/crm/inbox/{m.pk}/')
        self.assertContains(r, 'value="Re: Potvrda rezervacije ČĆ"')

    def test_reply_joins_the_thread_and_the_thread_reads_in_order(self):
        m = self.mail(
            subject=ENCODED,
            thread_key='guest@guest.test|old-encoded-key',
            body_text='first-in-thread',
            received_at=timezone.now() - timedelta(hours=1),
        )
        with mock.patch('plugins.installed.crm.inbox.smtplib.SMTP_SSL'):
            self.c.post(
                f'/dashboard/crm/inbox/{m.pk}/',
                {'to': 'guest@guest.test', 'subject': 'Re: x', 'body': 'second-in-thread'},
            )
        reply = MailMessage.objects.get(direction='out')
        self.assertEqual(reply.thread_key, m.thread_key)
        body = self.c.get(f'/dashboard/crm/inbox/{m.pk}/').content.decode()
        self.assertLess(body.index('first-in-thread'), body.index('second-in-thread'))


class InboxImportTests(_InboxCase):
    def test_encoded_headers_are_stored_decoded(self):
        raw = (
            b'From: =?UTF-8?Q?Ana_=C5=A0?= <ana@guest.test>\r\n'
            b'To: =?UTF-8?Q?Podr=C5=A1ka?= <support@shop.test>\r\n'
            b'Subject: =?UTF-8?B?UG90dnJkYSDEjA==?=\r\n'
            b'Message-ID: <import-1@guest.test>\r\n'
            b'Date: Mon, 27 Oct 2026 10:00:00 +0000\r\n'
            b'Content-Type: text/plain; charset=utf-8\r\n\r\nHello\r\n'
        )
        conn = mock.MagicMock()
        conn.uid.side_effect = lambda cmd, *a: (
            ('OK', [b'1']) if cmd == 'SEARCH' else ('OK', [(b'1 (RFC822 {1}', raw)])
        )
        with mock.patch('plugins.installed.crm.inbox.imaplib.IMAP4_SSL', return_value=conn):
            self.assertEqual(fetch_account(self.account), 1)
        m = MailMessage.objects.get(message_id='<import-1@guest.test>')
        self.assertEqual(m.subject, 'Potvrda Č')
        self.assertEqual(m.to_addresses, 'Podrška <support@shop.test>')
        self.assertEqual(m.from_address, 'ana@guest.test')


class MailAccountFormTests(_InboxCase):
    def test_a_port_that_is_not_a_number_is_an_error_not_a_crash(self):
        r = self.c.post(
            '/dashboard/crm/inbox/accounts/',
            {
                'label': 'Second',
                'email_address': 'two@shop.test',
                'imap_host': 'imap.shop.test',
                'smtp_host': 'smtp.shop.test',
                'imap_port': 'nine',
            },
        )
        self.assertContains(r, 'Ports are whole numbers')
        self.assertFalse(MailAccount.objects.filter(label='Second').exists())


class CrmOverviewTests(_InboxCase):
    def test_overdue_counts_only_open_tasks_past_due(self):
        now = timezone.now()
        CrmTask.objects.create(title='late', due_at=now - timedelta(hours=1))
        CrmTask.objects.create(title='soon', due_at=now + timedelta(hours=1))
        CrmTask.objects.create(title='done', due_at=now - timedelta(hours=1), completed_at=now)
        r = self.c.get('/dashboard/crm/')
        self.assertEqual(r.context['metrics']['overdue_tasks'], 1)
        self.assertEqual(r.context['metrics']['open_tasks'], 2)


class ChatThreadPageTests(_InboxCase):
    def setUp(self):
        super().setUp()
        self.thread = ChatThread.objects.create(email='c@guest.test')
        ChatMessage.objects.create(thread=self.thread, sender='customer', body='bubble-customer')
        ChatMessage.objects.create(thread=self.thread, sender='staff', body='bubble-staff')

    def test_messages_render_as_bubbles_not_toasts(self):
        r = self.c.get(f'/dashboard/crm/chat/{self.thread.id}/')
        self.assertContains(r, '<div class="crm-chat-text">bubble-customer</div>')
        self.assertContains(r, 'crm-chat-bubble crm-chat-staff')
        self.assertNotContains(r, '_toastQueue.push')
        self.assertNotContains(r, 'color:#fff')

    def test_closing_a_thread_says_so(self):
        r = self.c.post(f'/dashboard/crm/chat/{self.thread.id}/', {'action': 'close'}, follow=True)
        self.assertContains(r, 'message: "Thread closed."')


class LeadUpdateTests(_InboxCase):
    def test_a_later_signup_keeps_what_an_earlier_one_knew(self):
        from plugins.installed.crm.services import upsert_lead

        upsert_lead(
            email='lead@guest.test',
            first_name='Ana',
            phone='+38267000000',
            company='Kotor Tours',
            metadata={'form': 'contact'},
        )
        lead = upsert_lead(
            email='lead@guest.test', source='newsletter', metadata={'signup_source': 'footer'}
        )
        lead.refresh_from_db()
        self.assertEqual(
            (lead.first_name, lead.phone, lead.company), ('Ana', '+38267000000', 'Kotor Tours')
        )
        self.assertEqual(lead.source, 'newsletter')
        self.assertEqual(lead.metadata, {'form': 'contact', 'signup_source': 'footer'})

    def test_newsletter_items_in_the_activity_feed_link_to_a_page_that_exists(self):
        from plugins.installed.crm.app import CrmPlugin
        from plugins.installed.crm.services import upsert_lead

        upsert_lead(email='news@guest.test', source='newsletter')
        items = CrmPlugin.on_activity_feed(None, [])
        self.assertEqual(len(items), 1)
        self.assertEqual(self.c.get(items[0]['url']).status_code, 200)
