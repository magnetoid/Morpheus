"""Background tasks for the CRM inbox."""

from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.crm.tasks')


@app.task(name='crm.poll_mailboxes')
def poll_mailboxes() -> dict:
    """Walk every active MailAccount and import new mail.

    Driven by celery beat in production; the dashboard 'Sync now'
    button hits the same code path synchronously for instant feedback.
    """
    try:
        from plugins.installed.crm.inbox import fetch_all_active

        return fetch_all_active()
    except Exception as e:  # noqa: BLE001 — beat must keep running
        logger.warning('crm.tasks.poll_mailboxes failed: %s', e, exc_info=True)
        return {}


@app.task(name='crm.save_to_sent')
def save_to_sent(message_pk: str, raw: str) -> str:
    """File a message the CRM sent in its mailbox's Sent folder on the server."""
    from plugins.installed.crm import imap_sync
    from plugins.installed.crm.models import MailMessage

    message = MailMessage.objects.select_related('account').filter(pk=message_pk).first()
    if message is None or not message.account.is_active:
        return 'skipped'
    try:
        return imap_sync.save_to_sent(
            message.account, raw.encode('utf-8', 'surrogateescape'), message.message_id
        )
    except Exception as e:  # noqa: BLE001 — the mail went out; the copy is logged, not retried
        logger.warning('crm.tasks.save_to_sent %s failed: %s', message_pk, e)
        return 'failed'


@app.task(name='crm.push_read')
def push_read(message_pk: str) -> None:
    """Mark a message read on the server right after it is read in the CRM."""
    from plugins.installed.crm import imap_sync
    from plugins.installed.crm.models import MailMessage

    message = MailMessage.objects.select_related('account').filter(pk=message_pk).first()
    if message is None:
        return
    try:
        imap_sync.push_read(message)
    except Exception as e:  # noqa: BLE001 — the next poll pushes it again
        logger.warning('crm.tasks.push_read %s failed: %s', message_pk, e)
