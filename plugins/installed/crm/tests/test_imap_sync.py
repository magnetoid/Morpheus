"""The CRM inbox stays in step with the mailbox on the server, both ways (v0.195.0).

Until v0.195.0 the inbox only imported new mail: a read in either place stayed
there, mail deleted or archived on the server stayed in the CRM, a CRM reply
never reached the server's Sent folder and a reply sent from Gmail never reached
the CRM. These tests run the sync against a fake server that keeps the rules a
real one does: fetching ``BODY[]`` marks mail read and ``BODY.PEEK[]`` does not,
``UID n:*`` answers the highest UID when nothing is above ``n``, and a folder
can be renumbered (a new UIDVALIDITY).
"""

from __future__ import annotations

import re
from unittest import mock

from django.core.cache import cache

from plugins.installed.crm.inbox import fetch_account, send_message
from plugins.installed.crm.models import MailAccount, MailMessage
from plugins.installed.crm.tests.test_inbox_reading import _InboxCase


def _raw(mid: str, *, subject='Booking', sender='guest@guest.test', to='support@shop.test'):
    return (
        f'From: Guest <{sender}>\r\nTo: {to}\r\nSubject: {subject}\r\n'
        f'Message-ID: {mid}\r\nDate: Mon, 23 Nov 2026 10:00:00 +0000\r\n'
        'Content-Type: text/plain; charset=utf-8\r\n\r\nHello there\r\n'
    ).encode()


class Folder:
    def __init__(self, validity=1):
        self.validity, self.next_uid, self.msgs = validity, 1, {}

    def add(self, raw: bytes, *flags: str) -> int:
        uid = self.next_uid
        self.next_uid += 1
        self.msgs[uid] = [raw, set(flags)]
        return uid

    def renumber(self):
        """A new UIDVALIDITY: the same messages under new UIDs."""
        old = [self.msgs[u] for u in sorted(self.msgs)]
        self.validity += 1
        self.msgs, self.next_uid = {}, 100
        for raw, flags in old:
            self.add(raw, *flags)


class Server:
    def __init__(self):
        self.folders = {'INBOX': Folder(), 'Sent': Folder(7)}
        self.list_lines = [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Sent) "/" "Sent"']
        self.appended: list[bytes] = []
        self.fetch_specs: list[str] = []


class FakeConn:
    def __init__(self, server: Server):
        self.server, self.cur = server, None

    def login(self, *a):
        return 'OK', [b'logged in']

    def logout(self):
        return 'BYE', []

    def list(self):
        return 'OK', list(self.server.list_lines)

    def select(self, name):
        self.cur = self.server.folders.get(name.strip('"'))
        return ('OK', [str(len(self.cur.msgs)).encode()]) if self.cur else ('NO', [b'no folder'])

    def response(self, code):
        return code, [str(self.cur.validity).encode()]

    def append(self, folder, flags, when, raw):
        self.server.appended.append(raw)
        self.server.folders[folder.strip('"')].add(raw, '\\Seen')
        return 'OK', [b'appended']

    def uid(self, cmd, *args):
        msgs = self.cur.msgs
        if cmd == 'SEARCH':
            criteria = args[1]
            if criteria == 'ALL' or criteria.startswith('SINCE'):
                hits = sorted(msgs)
            elif criteria == 'SEEN':
                hits = sorted(u for u, (_r, f) in msgs.items() if '\\Seen' in f)
            elif criteria.startswith('UID '):
                low = int(criteria[4:].split(':')[0])
                hits = sorted(u for u in msgs if u >= low) or sorted(msgs)[-1:]
            elif criteria.startswith('HEADER Message-ID '):
                wanted = criteria.split(' ', 2)[2].strip('"')
                hits = [u for u, (r, _f) in msgs.items() if wanted.encode() in r]
            else:
                raise AssertionError(criteria)
            return 'OK', [' '.join(str(u) for u in hits).encode()]
        if cmd == 'FETCH':
            uids, spec = [int(u) for u in args[0].split(',')], args[1]
            self.server.fetch_specs.append(spec)
            out = []
            for n, uid in enumerate(uids, 1):
                if uid not in msgs:
                    continue
                raw, flags = msgs[uid]
                if 'BODY[]' in spec and 'PEEK' not in spec:
                    flags.add('\\Seen')
                literal = raw
                if 'HEADER.FIELDS' in spec:
                    found = re.search(rb'Message-ID: [^\r\n]+', raw)
                    literal = (found.group(0) if found else b'') + b'\r\n\r\n'
                meta = f'{n} (UID {uid} FLAGS ({" ".join(sorted(flags))}) BODY[] {{{len(literal)}}}'
                out += [(meta.encode(), literal), b')']
            return 'OK', out
        if cmd == 'STORE':
            for u in args[0].split(','):
                msgs[int(u)][1].add('\\Seen')
            return 'OK', []
        raise AssertionError(cmd)


class _SyncCase(_InboxCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.server = Server()
        self.inbox = self.server.folders['INBOX']
        self.sent = self.server.folders['Sent']
        patcher = mock.patch(
            'plugins.installed.crm.imap_sync.imaplib.IMAP4_SSL',
            side_effect=lambda *a, **k: FakeConn(self.server),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def sync(self) -> int:
        count = fetch_account(MailAccount.objects.get(pk=self.account.pk))
        self.account.refresh_from_db()
        self.assertEqual(self.account.last_error, '')
        return count

    def row(self, mid):
        return MailMessage.objects.get(account=self.account, message_id=mid)


class ImapSyncTests(_SyncCase):
    def test_new_mail_is_imported_without_marking_it_read_on_the_server(self):
        uid = self.inbox.add(_raw('<a@g.test>'))
        self.inbox.add(_raw('<b@g.test>'), '\\Seen')
        self.assertEqual(self.sync(), 2)
        a = self.row('<a@g.test>')
        self.assertEqual((a.imap_folder, a.imap_uid, a.is_read), ('INBOX', uid, False))
        self.assertTrue(self.row('<b@g.test>').is_read)
        self.assertNotIn('\\Seen', self.inbox.msgs[uid][1])
        self.assertTrue(all('PEEK' in spec for spec in self.server.fetch_specs))
        self.assertEqual(self.sync(), 0)
        self.assertEqual(MailMessage.objects.filter(direction='in').count(), 2)

    def test_read_on_the_server_is_read_here_and_back(self):
        uid = self.inbox.add(_raw('<a@g.test>'))
        self.sync()
        self.inbox.msgs[uid][1].add('\\Seen')
        self.sync()
        self.assertTrue(self.row('<a@g.test>').is_read)
        self.inbox.msgs[uid][1].discard('\\Seen')
        self.sync()
        self.assertFalse(self.row('<a@g.test>').is_read)

    def test_read_here_is_read_on_the_server(self):
        uid = self.inbox.add(_raw('<a@g.test>'))
        self.sync()
        with self.captureOnCommitCallbacks(execute=True):
            self.c.get(f'/dashboard/crm/inbox/{self.row("<a@g.test>").pk}/')
        self.assertIn('\\Seen', self.inbox.msgs[uid][1])
        row = self.row('<a@g.test>')
        self.assertTrue(row.is_read)
        self.assertFalse(row.seen_pending)

    def test_a_read_the_server_has_not_heard_of_is_pushed_not_undone(self):
        uid = self.inbox.add(_raw('<a@g.test>'))
        self.sync()
        MailMessage.objects.filter(message_id='<a@g.test>').update(is_read=True, seen_pending=True)
        self.sync()
        self.assertIn('\\Seen', self.inbox.msgs[uid][1])
        row = self.row('<a@g.test>')
        self.assertTrue(row.is_read)
        self.assertFalse(row.seen_pending)

    def test_mail_gone_from_the_server_leaves_the_inbox_and_keeps_its_page(self):
        uid = self.inbox.add(_raw('<a@g.test>', subject='gone-marker'))
        self.sync()
        del self.inbox.msgs[uid]
        self.sync()
        row = self.row('<a@g.test>')
        self.assertIsNotNone(row.removed_at)
        self.assertNotContains(self.c.get('/dashboard/crm/inbox/'), 'gone-marker')
        page = self.c.get(f'/dashboard/crm/inbox/{row.pk}/')
        self.assertContains(page, 'No longer in the mailbox on the server')
        # Put back (an undo, or moved back to the inbox): it returns.
        self.inbox.msgs[uid] = [_raw('<a@g.test>', subject='gone-marker'), set()]
        self.sync()
        self.assertIsNone(self.row('<a@g.test>').removed_at)

    def test_mail_sent_from_another_client_joins_the_thread(self):
        self.inbox.add(_raw('<q@g.test>', subject='Kayak tour'))
        self.sent.add(
            _raw(
                '<r@shop.test>',
                subject='Re: Kayak tour',
                sender='support@shop.test',
                to='guest@guest.test',
            ),
            '\\Seen',
        )
        self.sync()
        self.assertEqual(self.account.sent_folder, 'Sent')
        reply = self.row('<r@shop.test>')
        self.assertEqual((reply.direction, reply.imap_folder), ('out', 'Sent'))
        self.assertIsNotNone(reply.sent_at)
        self.assertEqual(reply.thread_key, self.row('<q@g.test>').thread_key)

    def _send(self):
        smtp = mock.MagicMock()
        with (
            mock.patch('plugins.installed.crm.inbox.smtplib.SMTP_SSL', return_value=smtp),
            self.captureOnCommitCallbacks(execute=True),
        ):
            return send_message(
                MailAccount.objects.get(pk=self.account.pk),
                to=['guest@guest.test'],
                subject='Your booking',
                body_text='See you there.',
            )

    def test_a_crm_reply_is_filed_in_the_sent_folder_once(self):
        self.sync()  # finds the Sent folder
        sent = self._send()
        self.assertTrue(sent.message_id.endswith('@shop.test>'))
        self.assertEqual(len(self.server.appended), 1)
        self.assertIn(sent.message_id.encode(), self.server.appended[0])
        self.sync()
        self.assertEqual(MailMessage.objects.filter(direction='out').count(), 1)
        self.assertEqual(self.row(sent.message_id).imap_folder, 'Sent')

    def test_a_server_that_files_sent_mail_itself_gets_no_second_copy(self):
        MailAccount.objects.filter(pk=self.account.pk).update(provider='gmail')
        self._send()
        self.assertEqual(self.server.appended, [])

    def test_a_renumbered_folder_is_matched_again_not_imported_twice(self):
        self.inbox.add(_raw('<a@g.test>'))
        self.inbox.add(_raw('<b@g.test>'), '\\Seen')
        self.sync()
        self.inbox.renumber()
        self.sync()
        self.assertEqual(MailMessage.objects.filter(direction='in').count(), 2)
        self.assertEqual(self.row('<a@g.test>').imap_uid, 100)
        self.assertIsNone(self.row('<a@g.test>').removed_at)

    def test_mail_imported_before_the_sync_gets_its_uid(self):
        uid = self.inbox.add(_raw('<old@g.test>'))
        old = self.mail(message_id='<old@g.test>', subject='old')
        MailAccount.objects.filter(pk=self.account.pk).update(last_uid=uid)
        self.inbox.msgs[uid][1].add('\\Seen')
        self.sync()
        old.refresh_from_db()
        self.assertEqual((old.imap_uid, old.is_read), (uid, True))
        self.assertEqual(MailMessage.objects.filter(direction='in').count(), 1)

    def test_pointing_the_account_at_another_folder_forgets_the_uids(self):
        self.inbox.add(_raw('<a@g.test>'))
        self.sync()
        self.server.folders['Support'] = Folder(validity=1)
        self.c.post(
            '/dashboard/crm/inbox/accounts/',
            {
                'id': str(self.account.pk),
                'label': 'Support',
                'email_address': 'support@shop.test',
                'imap_host': 'imap.shop.test',
                'smtp_host': 'smtp.shop.test',
                'imap_folder': 'Support',
                'is_active': 'on',
                'imap_use_ssl': 'on',
            },
        )
        self.account.refresh_from_db()
        self.assertEqual((self.account.uid_validity, self.account.last_uid), (0, 0))
        self.sync()
        # The old folder's message is not "removed": it was never in the new folder.
        self.assertIsNone(self.row('<a@g.test>').removed_at)

    def test_one_sync_per_mailbox_at_a_time(self):
        self.inbox.add(_raw('<a@g.test>'))
        from plugins.installed.crm import imap_sync

        self.assertTrue(imap_sync.account_lock(self.account))
        self.assertEqual(fetch_account(self.account), 0)
        imap_sync.release_lock(self.account)
        self.assertEqual(self.sync(), 1)

    def test_encoded_headers_are_stored_decoded(self):
        self.inbox.add(
            b'From: =?UTF-8?Q?Ana_=C5=A0?= <ana@guest.test>\r\n'
            b'To: =?UTF-8?Q?Podr=C5=A1ka?= <support@shop.test>\r\n'
            b'Subject: =?UTF-8?B?UG90dnJkYSDEjA==?=\r\n'
            b'Message-ID: <import-1@guest.test>\r\n'
            b'Date: Mon, 27 Oct 2026 10:00:00 +0000\r\n'
            b'Content-Type: text/plain; charset=utf-8\r\n\r\nHello\r\n'
        )
        self.assertEqual(self.sync(), 1)
        m = self.row('<import-1@guest.test>')
        self.assertEqual(m.subject, 'Potvrda Č')
        self.assertEqual(m.to_addresses, 'Podrška <support@shop.test>')
        self.assertEqual(m.from_address, 'ana@guest.test')


class ImapSyncReviewTests(_SyncCase):
    """The three holes the review of v0.195.0 found."""

    def test_an_immediate_read_waits_when_the_folder_was_renumbered(self):
        first = self.inbox.add(_raw('<a@g.test>'))
        self.sync()
        self.inbox.renumber()  # <a> is UID 100 now; UID 1 is free for another message
        other = self.inbox.add(_raw('<other@g.test>'))
        self.inbox.msgs[first] = self.inbox.msgs.pop(other)
        with self.captureOnCommitCallbacks(execute=True):
            self.c.get(f'/dashboard/crm/inbox/{self.row("<a@g.test>").pk}/')
        self.assertNotIn('\\Seen', self.inbox.msgs[first][1])  # the other message stays unread
        self.assertTrue(self.row('<a@g.test>').seen_pending)
        self.sync()  # matched again, then pushed
        self.assertIn('\\Seen', self.inbox.msgs[100][1])
        self.assertFalse(self.row('<a@g.test>').seen_pending)

    def test_a_broker_that_is_down_leaves_the_read_to_the_poll(self):
        self.inbox.add(_raw('<a@g.test>'))
        self.sync()
        with (
            mock.patch(
                'plugins.installed.crm.tasks.push_read.delay', side_effect=ConnectionError('down')
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.c.get(f'/dashboard/crm/inbox/{self.row("<a@g.test>").pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.row('<a@g.test>').seen_pending)

    def test_a_renumbered_sent_folder_keeps_its_old_mail(self):
        from datetime import timedelta

        from django.utils import timezone

        self.sync()  # finds the Sent folder
        self.sent.add(_raw('<old-reply@shop.test>', sender='support@shop.test'), '\\Seen')
        old = MailMessage.objects.create(
            account=self.account,
            direction='out',
            message_id='<old-reply@shop.test>',
            from_address='support@shop.test',
            sent_at=timezone.now() - timedelta(days=200),
        )
        MailAccount.objects.filter(pk=self.account.pk).update(sent_last_uid=1)
        MailMessage.objects.filter(pk=old.pk).update(imap_folder='Sent', imap_uid=1)
        with (
            mock.patch('plugins.installed.crm.imap_sync.SENT_LOOKBACK_DAYS', 0),
            mock.patch.object(FakeConn, 'uid', _no_recent(FakeConn.uid)),
        ):
            self.sent.renumber()
            self.sync()
        old.refresh_from_db()
        self.assertEqual(old.imap_uid, 100)


def _no_recent(uid):
    """``SINCE`` finds nothing: every message in the folder is older than the lookback."""

    def wrapped(self, cmd, *args):
        if cmd == 'SEARCH' and str(args[1]).startswith('SINCE'):
            return 'OK', [b'']
        return uid(self, cmd, *args)

    return wrapped
