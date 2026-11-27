"""IMAP fetch + SMTP send for the CRM inbox.

Design notes:

* IMAP: a two-way sync per folder (`crm.imap_sync`): new mail is imported by
  UID from `MailAccount.last_uid`, reads go both ways, mail gone from the
  server leaves the inbox, and the server's Sent folder is synced too.
  `imaplib` is in the stdlib — no extra dependency.
* SMTP: we send via `smtplib.SMTP_SSL` or `SMTP.starttls()` based on
  the account's flags, then persist a `MailMessage(direction='out')` so
  the thread view shows both sides of the conversation.
* Customer matching is done by exact email match against `Customer.email`
  in either the From (inbound) or To (outbound) header. Misses leave
  the row unlinked — the dashboard renders the address verbatim.
"""

from __future__ import annotations

import email
import logging
import re
import smtplib
from collections.abc import Iterable
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, parseaddr

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from plugins.installed.crm.mail_render import header_text

logger = logging.getLogger('morpheus.crm.inbox')


def _normalise_subject(subj: str) -> str:
    """Strip Re:/Fwd: prefixes, lowercase, collapse whitespace."""
    s = (subj or '').strip()
    while True:
        m = re.match(r'^(re|fwd|fw)\s*:\s*', s, flags=re.I)
        if not m:
            break
        s = s[m.end() :]
    return re.sub(r'\s+', ' ', s).lower()


def _thread_key(subject: str, counterparty_email: str) -> str:
    return f'{counterparty_email.lower()}|{_normalise_subject(subject)}'


def _match_customer(email_address: str):
    if not email_address:
        return None
    User = get_user_model()
    try:
        return User.objects.filter(email__iexact=email_address.strip()).first()
    except Exception:  # noqa: BLE001
        return None


def _decode_payload(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ''
    charset = part.get_content_charset() or 'utf-8'
    try:
        return payload.decode(charset, errors='replace')
    except (LookupError, UnicodeDecodeError):
        return payload.decode('utf-8', errors='replace')


def _extract_bodies(msg: email.message.Message) -> tuple[str, str]:
    text, html = '', ''
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get('Content-Disposition') or '').lower()
            if 'attachment' in disp:
                continue
            if ctype == 'text/plain' and not text:
                text = _decode_payload(part)
            elif ctype == 'text/html' and not html:
                html = _decode_payload(part)
    else:
        ctype = msg.get_content_type()
        body = _decode_payload(msg)
        if ctype == 'text/html':
            html = body
        else:
            text = body
    return text, html


def fetch_account(account, *, max_messages: int = 200) -> int:
    """Sync one MailAccount with its server both ways; the number of new messages.

    The inbox folder, then the server's Sent folder (``crm.imap_sync``): new mail
    is imported, reads go both ways and mail gone from the server leaves the inbox.
    """
    from plugins.installed.crm import imap_sync

    if not account.is_active:
        return 0
    if not imap_sync.account_lock(account):
        return 0  # another poll or Sync now is on this mailbox
    try:
        return _sync_account(account, max_messages=max_messages)
    finally:
        imap_sync.release_lock(account)


def _sync_account(account, *, max_messages: int) -> int:
    from plugins.installed.crm import imap_sync

    try:
        conn = imap_sync.connect(account)
    except Exception as e:  # noqa: BLE001
        account.last_error = f'connect: {e}'[:1000]
        account.last_polled_at = timezone.now()
        account.save(update_fields=['last_error', 'last_polled_at'])
        logger.warning('crm.inbox: %s connect failed: %s', account.label, e)
        return 0

    imported = 0
    step = 'fetch'
    try:
        imported = imap_sync.sync_folder(
            conn,
            account,
            account.imap_folder or 'INBOX',
            sent=False,
            max_messages=max_messages,
            importer=lambda *a: _import(account, *a),
        )
        step = 'sent folder'
        if not account.sent_folder:
            account.sent_folder = imap_sync.find_sent_folder(conn)
            account.save(update_fields=['sent_folder'])
        if account.sent_folder and account.sent_folder != (account.imap_folder or 'INBOX'):
            imap_sync.sync_folder(
                conn,
                account,
                account.sent_folder,
                sent=True,
                max_messages=max_messages,
                importer=lambda *a: _import(account, *a),
            )
    except Exception as e:  # noqa: BLE001
        logger.warning('crm.inbox: %s %s failed: %s', account.label, step, e, exc_info=True)
        account.last_error = f'{step}: {e}'[:1000]
    else:
        account.last_error = ''
    imap_sync.logout(conn)

    account.last_polled_at = timezone.now()
    account.save(update_fields=['last_polled_at', 'last_error'])
    if imported:
        logger.info('crm.inbox: %s imported %d new message(s)', account.label, imported)
    return imported


def _import(account, raw: bytes, uid: int, folder: str, flags: set, direction: str) -> bool:
    """Store one message the server holds; False when it cannot be read."""
    from plugins.installed.crm import imap_sync
    from plugins.installed.crm.models import MailMessage

    try:
        msg = email.message_from_bytes(raw)
    except Exception:  # noqa: BLE001
        logger.warning('crm.inbox: %s could not parse UID %s', account.label, uid)
        return False

    mid = (msg.get('Message-ID') or '').strip()
    _from_name, from_addr = parseaddr(msg.get('From', ''))
    # Headers arrive RFC 2047 encoded (=?UTF-8?Q?…?=); store them as people read them.
    to_addrs = [header_text(a) for a in msg.get_all('To', []) or []]
    cc_addrs = [header_text(a) for a in msg.get_all('Cc', []) or []]
    subject = header_text(msg.get('Subject')).strip()
    when = imap_sync.received_at(msg)
    text, html = _extract_bodies(msg)
    # The other side of the conversation: the sender of mail we got, the first
    # recipient of mail we sent.
    counterparty = from_addr if direction == 'in' else parseaddr(', '.join(to_addrs))[1]
    MailMessage.objects.create(
        account=account,
        direction=direction,
        message_id=mid[:255],
        in_reply_to=(msg.get('In-Reply-To') or '').strip()[:255],
        thread_key=_thread_key(subject, counterparty or ''),
        from_address=(from_addr or '')[:320],
        to_addresses=', '.join(to_addrs)[:5000],
        cc_addresses=', '.join(cc_addrs)[:5000],
        subject=subject[:500],
        body_text=text or '',
        body_html=html or '',
        customer=_match_customer(counterparty),
        is_read=direction == 'out' or '\\Seen' in flags,
        imap_folder=folder,
        imap_uid=uid,
        received_at=when if direction == 'in' else None,
        sent_at=when if direction == 'out' else None,
    )
    return True


def send_message(
    account,
    *,
    to: Iterable[str],
    subject: str,
    body_text: str,
    body_html: str = '',
    cc: Iterable[str] | None = None,
    in_reply_to: str = '',
    customer=None,
    thread_key: str = '',
):
    """Send an email and persist a MailMessage(direction='out').

    A reply passes its message's ``thread_key`` so it joins that thread whatever
    the subject now reads.
    """
    from plugins.installed.crm.models import MailMessage

    to_list = [a.strip() for a in to if a and a.strip()]
    cc_list = [a.strip() for a in (cc or []) if a and a.strip()]
    if not to_list:
        raise ValueError('At least one recipient is required.')

    if body_html:
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(body_text or '', 'plain', 'utf-8'))
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))
    else:
        msg = MIMEText(body_text or '', 'plain', 'utf-8')

    msg['From'] = account.email_address
    msg['To'] = ', '.join(to_list)
    if cc_list:
        msg['Cc'] = ', '.join(cc_list)
    msg['Subject'] = subject or ''
    # Our own Message-ID: the Sent folder copy is found by it, so the sync matches
    # it to this row instead of importing it a second time.
    message_id = make_msgid(domain=(account.email_address.rpartition('@')[2] or None))
    msg['Message-ID'] = message_id
    msg['Date'] = formatdate(localtime=False)
    if in_reply_to:
        msg['In-Reply-To'] = in_reply_to
        msg['References'] = in_reply_to

    all_recipients = to_list + cc_list

    try:
        if account.smtp_use_ssl:
            smtp = smtplib.SMTP_SSL(account.smtp_host, account.smtp_port, timeout=30)
        else:
            smtp = smtplib.SMTP(account.smtp_host, account.smtp_port, timeout=30)
            if account.smtp_use_tls:
                smtp.starttls()
        smtp.login(account.smtp_username, account.smtp_password)
        smtp.sendmail(account.email_address, all_recipients, msg.as_string())
        smtp.quit()
    except Exception as e:  # noqa: BLE001 — caller logs / surfaces error
        logger.warning('crm.inbox: %s send failed: %s', account.label, e, exc_info=True)
        raise

    sent = MailMessage.objects.create(
        account=account,
        direction='out',
        message_id=message_id[:255],
        in_reply_to=in_reply_to[:255],
        thread_key=thread_key or _thread_key(subject, to_list[0]),
        from_address=account.email_address,
        to_addresses=', '.join(to_list)[:5000],
        cc_addresses=', '.join(cc_list)[:5000],
        subject=subject[:500] if subject else '',
        body_text=body_text or '',
        body_html=body_html or '',
        customer=customer or _match_customer(to_list[0]),
        is_read=True,
        sent_at=timezone.now(),
    )
    raw = msg.as_bytes()
    transaction.on_commit(lambda: _queue_save_to_sent(sent.pk, raw))
    return sent


def _queue_save_to_sent(message_pk, raw: bytes) -> None:
    from plugins.installed.crm.tasks import save_to_sent

    try:
        save_to_sent.delay(str(message_pk), raw.decode('utf-8', 'surrogateescape'))
    except Exception as e:  # noqa: BLE001 — the mail is sent; the server copy is a convenience
        logger.warning('crm.inbox: could not queue the Sent copy of %s: %s', message_pk, e)


def fetch_all_active(*, max_per_account: int = 200) -> dict:
    """Poll every active mail account once. Returns {label: count}."""
    from plugins.installed.crm.models import MailAccount

    counts = {}
    for acc in MailAccount.objects.filter(is_active=True):
        try:
            counts[acc.label] = fetch_account(acc, max_messages=max_per_account)
        except Exception as e:  # noqa: BLE001
            logger.warning('crm.inbox: %s poll crashed: %s', acc.label, e, exc_info=True)
            counts[acc.label] = 0
    return counts
