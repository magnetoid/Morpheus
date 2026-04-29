"""Backup task — celery wrapper around the morph_backup command.

We don't reimplement backup logic here; the command in
``core/management/commands/morph_backup.py`` is the source of truth and
also runs from the CLI. This task lets celery beat invoke it on the
configured schedule.
"""
from __future__ import annotations

import io
import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger("morpheus.backups")


def _config() -> dict:
    """Read plugin config; default to including media."""
    try:
        from plugins.registry import plugin_registry
        plugin = plugin_registry.get('backups')
        if plugin is not None:
            return {'include_media': bool(plugin.get_config_value('include_media', True))}
    except Exception:  # noqa: BLE001 — DB may not be ready
        pass
    return {'include_media': True}


@shared_task(bind=True, time_limit=60 * 60, soft_time_limit=60 * 55)
def run_backup(self) -> dict:
    """Invoke `manage.py morph_backup`. Returns a small status dict."""
    cfg = _config()
    args: list[str] = []
    if not cfg['include_media']:
        args.append('--no-media')

    out = io.StringIO()
    try:
        call_command('morph_backup', *args, stdout=out, stderr=out)
        msg = out.getvalue().strip().splitlines()[-1] if out.getvalue() else ''
        logger.info('backups.run_backup: %s', msg)
        return {'ok': True, 'last_line': msg[:200]}
    except Exception as e:  # noqa: BLE001 — log + retry next day
        logger.error('backups.run_backup failed: %s', e, exc_info=True)
        return {'ok': False, 'error': str(e)[:200]}
