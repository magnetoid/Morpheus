"""Two-way IMAP sync for the CRM inbox (v0.195.0).

Until v0.195.0 the inbox only imported: it opened the mailbox read-only, walked
forward from the last UID and kept no message's UID, so a message read in the
CRM stayed unread in Gmail (and the other way round), mail deleted or archived
on the server stayed in the CRM, a CRM reply never reached the server's Sent
folder and a reply sent from Gmail never reached the CRM.

Each poll, per folder (the inbox folder, then the server's Sent folder):

1. Select the folder and read its UIDVALIDITY. A first sync matches the rows
   already stored to their UIDs by Message-ID; a changed value (the server
   renumbered the folder) clears the stored UIDs and walks the folder again.
2. Push the reads made in the CRM (``seen_pending``) as ``\\Seen``.
3. Walk the UIDs above the last one seen: a Message-ID the account already holds
   is attached to that row, anything else is imported (``BODY.PEEK``, so the
   import never marks mail read on the server).
4. Read which UIDs are still there and which are ``\\Seen``: a row whose UID is
   gone is removed from the inbox (``removed_at``; it stays in the thread and the
   contact's history), and a received row takes the server's read state.

Nothing is ever deleted on the server: the CRM only sets ``\\Seen`` and saves its
own replies to the Sent folder.
"""

from __future__ import annotations

import email
import imaplib
import logging
import re
import time
from datetime import UTC, timedelta

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('morpheus.crm.imap_sync')

# Names a server's Sent folder goes by when it does not flag one \Sent (RFC 6154).
SENT_NAMES = (
    'sent',
    'sent items',
    'sent messages',
    'sent mail',
    'inbox.sent',
    'inbox/sent',
    '[gmail]/sent mail',
    '[google mail]/sent mail',
    'poslato',
    'poslate poruke',
)
# Providers whose SMTP server files every message it sends in the Sent folder
# itself, so the CRM must not save a second copy.
SAVES_SENT_ITSELF = {'gmail'}
HEADER_BATCH = 500  # UIDs per header fetch
WALK_LIMIT = 2000  # UIDs looked at per folder per poll
SENT_LOOKBACK_DAYS = 30  # a first Sent sync imports this far back
LOCK_SECONDS = 600

_UID = re.compile(rb'UID (\d+)')
_FLAGS = re.compile(rb'FLAGS \(([^)]*)\)')
_LIST = re.compile(rb'^\((?P<attrs>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)$')


class SyncError(Exception):
    """The server refused a step; the message says which."""


def quote(folder: str) -> str:
    """A folder name as an IMAP astring: quoted when it holds a space or a quote."""
    if folder and re.fullmatch(r'[A-Za-z0-9_./\[\]-]+', folder):
        return folder
    return '"' + folder.replace('\\', '\\\\').replace('"', '\\"') + '"'


def connect(account):
    conn = (
        imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
        if account.imap_use_ssl
        else imaplib.IMAP4(account.imap_host, account.imap_port)
    )
    conn.login(account.imap_username, account.imap_password)
    return conn


def logout(conn) -> None:
    try:  # noqa: SIM105
        conn.logout()
    except Exception:  # noqa: BLE001, S110 — the work is done; a failed goodbye is not news
        pass


def account_lock(account):
    """True when this process may sync ``account`` now (one sync per mailbox at a time)."""
    return cache.add(f'crm:imap-sync:{account.pk}', 1, LOCK_SECONDS)


def release_lock(account) -> None:
    cache.delete(f'crm:imap-sync:{account.pk}')


def select(conn, folder: str) -> int:
    """Open ``folder`` read-write; its UIDVALIDITY (0 when the server names none)."""
    typ, _data = conn.select(quote(folder))
    if typ != 'OK':
        raise SyncError(f'select {folder}: {typ}')
    _typ, data = conn.response('UIDVALIDITY')
    try:
        return int((data or [b'0'])[0] or 0)
    except (TypeError, ValueError):
        return 0


def search(conn, criteria: str) -> list[int]:
    typ, data = conn.uid('SEARCH', None, criteria)
    if typ != 'OK':
        raise SyncError(f'search {criteria}: {typ}')
    raw = (data or [b''])[0] or b''
    return sorted({int(u) for u in raw.split() if u.isdigit()})


def _parts(data) -> list[tuple[bytes, bytes]]:
    """A FETCH answer as ``[(everything but the literal, the literal)]`` per message."""
    out: list[tuple[bytes, bytes]] = []
    for item in data or []:
        if isinstance(item, tuple) and len(item) >= 2:
            out.append((bytes(item[0]), bytes(item[1] or b'')))
        elif isinstance(item, bytes) and out:
            # A server may send FLAGS after the literal: b' FLAGS (\\Seen))'.
            meta, literal = out[-1]
            out[-1] = (meta + item, literal)
    return out


def _flags(meta: bytes) -> set[str]:
    found = _FLAGS.search(meta)
    return set(found.group(1).decode('ascii', 'replace').split()) if found else set()


def fetch_headers(conn, uids: list[int]) -> dict[int, tuple[str, set[str]]]:
    """``{uid: (message_id, flags)}``, read without marking anything read."""
    out: dict[int, tuple[str, set[str]]] = {}
    for start in range(0, len(uids), HEADER_BATCH):
        chunk = uids[start : start + HEADER_BATCH]
        typ, data = conn.uid(
            'FETCH',
            ','.join(str(u) for u in chunk),
            '(UID FLAGS BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])',
        )
        if typ != 'OK':
            raise SyncError(f'fetch headers: {typ}')
        for meta, literal in _parts(data):
            uid = _UID.search(meta)
            if not uid:
                continue
            mid = (email.message_from_bytes(literal).get('Message-ID') or '').strip()
            out[int(uid.group(1))] = (mid[:255], _flags(meta))
    return out


def fetch_message(conn, uid: int) -> tuple[bytes, set[str]] | None:
    typ, data = conn.uid('FETCH', str(uid), '(UID FLAGS BODY.PEEK[])')
    if typ != 'OK':
        return None
    parts = _parts(data)
    if not parts:
        return None
    meta, literal = parts[0]
    return literal, _flags(meta)


def find_sent_folder(conn) -> str:
    """The folder the server flags ``\\Sent``, else one named like a Sent folder."""
    try:
        typ, data = conn.list()
    except Exception:  # noqa: BLE001
        return ''
    if typ != 'OK':
        return ''
    named = ''
    for line in data or []:
        if not isinstance(line, bytes):
            continue
        found = _LIST.match(line.strip())
        if not found:
            continue
        name = found.group('name').decode('utf-8', 'replace').strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1].replace('\\"', '"').replace('\\\\', '\\')
        if '\\sent' in found.group('attrs').decode('ascii', 'replace').lower().split():
            return name
        if not named and name.lower() in SENT_NAMES:
            named = name
    return named


def _state(account, sent: bool) -> tuple[str, str]:
    return ('sent_uid_validity', 'sent_last_uid') if sent else ('uid_validity', 'last_uid')


def sync_folder(conn, account, folder: str, *, sent: bool, max_messages: int, importer) -> int:
    """Sync one folder both ways; the number of messages imported.

    ``importer(raw, uid, folder, flags, direction)`` stores one new message.
    """
    from plugins.installed.crm.models import MailMessage

    direction = 'out' if sent else 'in'
    validity_field, last_field = _state(account, sent)
    rows = MailMessage.objects.filter(account=account)
    validity = select(conn, folder)
    stored = getattr(account, validity_field)
    last_uid = getattr(account, last_field)

    if stored and validity and stored != validity:
        # The server renumbered the folder: every stored UID names another message.
        rows.filter(imap_folder=folder).update(imap_uid=None)
        last_uid = 0
    if validity and stored != validity:  # a first sync, or a renumbered folder
        if sent and not last_uid:
            # A first Sent sync starts a month back, not at the account's first mail.
            since = (timezone.now() - timedelta(days=SENT_LOOKBACK_DAYS)).strftime('%d-%b-%Y')
            recent = search(conn, f'SINCE {since}')
            everything = search(conn, 'ALL')
            last_uid = (recent[0] - 1) if recent else (everything[-1] if everything else 0)
        else:
            _attach(
                conn, rows, folder, direction, [u for u in search(conn, 'ALL') if u <= last_uid]
            )
        setattr(account, validity_field, validity)

    if not sent:
        _push_reads(conn, rows.filter(imap_folder=folder))

    imported = 0
    new = [u for u in search(conn, f'UID {last_uid + 1}:*') if u > last_uid][:WALK_LIMIT]
    headers = fetch_headers(conn, new) if new else {}
    for uid in new:
        mid, flags = headers.get(uid, ('', set()))
        if mid and _attach_one(rows, folder, direction, uid, mid, flags):
            last_uid = uid
            continue
        if imported >= max_messages:
            break
        fetched = fetch_message(conn, uid)
        if fetched is not None:
            raw, flags = fetched
            if importer(raw, uid, folder, flags, direction):
                imported += 1
        last_uid = uid
    setattr(account, last_field, last_uid)
    account.save(update_fields=[validity_field, last_field])

    _mirror(conn, rows.filter(imap_folder=folder, imap_uid__isnull=False), read_state=not sent)
    return imported


def _attach(conn, rows, folder: str, direction: str, uids: list[int]) -> None:
    """Give the stored rows the UIDs their Message-IDs have in ``folder``."""
    waiting = rows.filter(direction=direction, imap_uid__isnull=True).exclude(message_id='')
    if not uids or not waiting.exists():
        return
    for uid, (mid, flags) in fetch_headers(conn, uids).items():
        if mid:
            _attach_one(waiting, folder, direction, uid, mid, flags)


def _attach_one(rows, folder, direction, uid, mid, flags) -> bool:
    """Point the account's row with this Message-ID at ``uid``; False when there is none."""
    row = rows.filter(direction=direction, message_id=mid).order_by('created_at').first()
    if row is None:
        return False
    row.imap_folder, row.imap_uid, row.removed_at = folder, uid, None
    fields = ['imap_folder', 'imap_uid', 'removed_at']
    if direction == 'in' and not row.seen_pending:
        row.is_read = '\\Seen' in flags
        fields.append('is_read')
    row.save(update_fields=fields)
    return True


def _push_reads(conn, rows) -> None:
    """Mark read on the server what was read in the CRM."""
    pending = list(rows.filter(seen_pending=True, imap_uid__isnull=False))
    if not pending:
        return
    uids = ','.join(str(r.imap_uid) for r in pending)
    typ, _ = conn.uid('STORE', uids, '+FLAGS', '(\\Seen)')
    if typ != 'OK':
        raise SyncError(f'store \\Seen: {typ}')
    rows.filter(pk__in=[r.pk for r in pending]).update(seen_pending=False)


def _mirror(conn, rows, *, read_state: bool) -> None:
    """Take the server's word for what is still there and what has been read."""
    present = set(search(conn, 'ALL'))
    seen = set(search(conn, 'SEEN')) if read_state else set()
    now = timezone.now()
    gone, back, read, unread = [], [], [], []
    for pk, uid, is_read, removed_at, pending, direction in rows.values_list(
        'pk', 'imap_uid', 'is_read', 'removed_at', 'seen_pending', 'direction'
    ):
        if uid not in present:
            if removed_at is None:
                gone.append(pk)
            continue
        if removed_at is not None:
            back.append(pk)
        if read_state and direction == 'in' and not pending:
            if uid in seen and not is_read:
                read.append(pk)
            elif uid not in seen and is_read:
                unread.append(pk)
    for pks, values in (
        (gone, {'removed_at': now}),
        (back, {'removed_at': None}),
        (read, {'is_read': True}),
        (unread, {'is_read': False}),
    ):
        for start in range(0, len(pks), 500):
            rows.model.objects.filter(pk__in=pks[start : start + 500]).update(**values)


def push_read(message) -> None:
    """Mark one message read on the server now (the poll retries when this fails)."""
    account = message.account
    if not (message.seen_pending and message.imap_uid and account.is_active):
        return
    conn = connect(account)
    try:
        select(conn, message.imap_folder or account.imap_folder or 'INBOX')
        _push_reads(conn, type(message).objects.filter(pk=message.pk))
    finally:
        logout(conn)


def save_to_sent(account, raw: bytes, message_id: str) -> str:
    """File a message the CRM sent in the server's Sent folder; what happened.

    Gmail's SMTP server files it itself. Elsewhere the folder is searched for the
    Message-ID first, so a server that also files sent mail gets no second copy.
    """
    if account.provider in SAVES_SENT_ITSELF:
        return 'server files it'
    conn = connect(account)
    try:
        folder = account.sent_folder or find_sent_folder(conn)
        if not folder:
            return 'no sent folder'
        if not account.sent_folder:
            account.sent_folder = folder
            account.save(update_fields=['sent_folder'])
        select(conn, folder)
        if message_id and search(conn, f'HEADER Message-ID {quote(message_id)}'):
            return 'already there'
        typ, _ = conn.append(quote(folder), '(\\Seen)', imaplib.Time2Internaldate(time.time()), raw)
        if typ != 'OK':
            raise SyncError(f'append {folder}: {typ}')
        return 'saved'
    finally:
        logout(conn)


def received_at(msg) -> object:
    from email.utils import parsedate_to_datetime

    try:
        when = parsedate_to_datetime(msg['Date']) if msg.get('Date') else None
    except Exception:  # noqa: BLE001
        when = None
    if when is not None and when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when or timezone.now()
