"""IMAP fetch + SMTP send for the CRM inbox.

Design notes:

* IMAP: we use UID-based fetching and persist `MailAccount.last_uid`, so
  re-running the poller is idempotent and doesn't re-import old mail.
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
import imaplib
import logging
import re
import smtplib
from datetime import datetime, timezone as dt_timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr, parsedate_to_datetime
from typing import Iterable

from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger('morpheus.crm.inbox')


def _normalise_subject(subj: str) -> str:
    """Strip Re:/Fwd: prefixes, lowercase, collapse whitespace."""
    s = (subj or '').strip()
    while True:
        m = re.match(r'^(re|fwd|fw)\s*:\s*', s, flags=re.I)
        if not m:
            break
        s = s[m.end():]
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
    """Pull new messages for one MailAccount via IMAP. Returns count imported."""
    from plugins.installed.crm.models import MailMessage

    if not account.is_active:
        return 0

    try:
        if account.imap_use_ssl:
            conn = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
        else:
            conn = imaplib.IMAP4(account.imap_host, account.imap_port)
        conn.login(account.imap_username, account.imap_password)
        conn.select(account.imap_folder, readonly=True)
    except Exception as e:  # noqa: BLE001
        account.last_error = f'connect: {e}'[:1000]
        account.last_polled_at = timezone.now()
        account.save(update_fields=['last_error', 'last_polled_at'])
        logger.warning('crm.inbox: %s connect failed: %s', account.label, e)
        return 0

    imported = 0
    try:
        # UID search "since last_uid+1" — IMAP UID range is inclusive.
        start_uid = (account.last_uid or 0) + 1
        typ, data = conn.uid('SEARCH', None, f'UID {start_uid}:*')
        if typ != 'OK' or not data or not data[0]:
            return 0
        uids = [int(u) for u in data[0].split() if int(u) >= start_uid]
        uids.sort()
        if max_messages:
            uids = uids[:max_messages]

        for uid in uids:
            typ, raw = conn.uid('FETCH', str(uid), '(RFC822)')
            if typ != 'OK' or not raw or not raw[0]:
                continue
            try:
                msg = email.message_from_bytes(raw[0][1])
            except Exception:  # noqa: BLE001
                logger.warning('crm.inbox: %s could not parse UID %s', account.label, uid)
                account.last_uid = max(account.last_uid, uid)
                continue

            mid = (msg.get('Message-ID') or '').strip()
            if mid and MailMessage.objects.filter(message_id=mid).exists():
                account.last_uid = max(account.last_uid, uid)
                continue

            from_name, from_addr = parseaddr(msg.get('From', ''))
            to_addrs = msg.get_all('To', []) or []
            cc_addrs = msg.get_all('Cc', []) or []
            subject = (msg.get('Subject') or '').strip()
            in_reply_to = (msg.get('In-Reply-To') or '').strip()

            received_at = None
            try:
                if msg.get('Date'):
                    received_at = parsedate_to_datetime(msg['Date'])
                    if received_at and received_at.tzinfo is None:
                        received_at = received_at.replace(tzinfo=dt_timezone.utc)
            except Exception:  # noqa: BLE001
                received_at = timezone.now()
            received_at = received_at or timezone.now()

            text, html = _extract_bodies(msg)

            MailMessage.objects.create(
                account=account,
                direction='in',
                message_id=mid[:255],
                in_reply_to=in_reply_to[:255],
                thread_key=_thread_key(subject, from_addr),
                from_address=(from_addr or '')[:320],
                to_addresses=', '.join(to_addrs)[:5000],
                cc_addresses=', '.join(cc_addrs)[:5000],
                subject=subject[:500],
                body_text=text or '',
                body_html=html or '',
                customer=_match_customer(from_addr),
                received_at=received_at,
            )
            imported += 1
            account.last_uid = max(account.last_uid, uid)
    except Exception as e:  # noqa: BLE001
        logger.warning('crm.inbox: %s fetch failed: %s', account.label, e, exc_info=True)
        account.last_error = f'fetch: {e}'[:1000]
    else:
        account.last_error = ''

    try:
        conn.logout()
    except Exception:  # noqa: BLE001
        pass

    account.last_polled_at = timezone.now()
    account.save(update_fields=['last_uid', 'last_polled_at', 'last_error'])
    if imported:
        logger.info('crm.inbox: %s imported %d new message(s)', account.label, imported)
    return imported


def send_message(
    account, *,
    to: Iterable[str],
    subject: str,
    body_text: str,
    body_html: str = '',
    cc: Iterable[str] | None = None,
    in_reply_to: str = '',
    customer=None,
):
    """Send an email and persist a MailMessage(direction='out')."""
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

    return MailMessage.objects.create(
        account=account,
        direction='out',
        in_reply_to=in_reply_to[:255],
        thread_key=_thread_key(subject, to_list[0]),
        from_address=account.email_address,
        to_addresses=', '.join(to_list)[:5000],
        cc_addresses=', '.join(cc_list)[:5000],
        subject=subject[:500] if subject else '',
        body_text=body_text or '',
        body_html=body_html or '',
        customer=customer or _match_customer(to_list[0]),
        sent_at=timezone.now(),
    )


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
