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
