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

logger = logging.getLogger('morpheus.backups')


def _config() -> dict:
    """Read plugin config. Blank values fall through to the command's own
    defaults (MORPHEUS_BACKUP_DIR / MORPHEUS_BACKUP_KEEP, else the worker's
    persistent /app/backups volume and 7 copies)."""
    cfg: dict = {'include_media': True, 'backup_dir': '', 'retention_count': None}
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('backups')
        if plugin is not None:
            cfg['include_media'] = bool(plugin.get_config_value('include_media', True))
            cfg['backup_dir'] = str(plugin.get_config_value('backup_dir', '') or '').strip()
            keep = plugin.get_config_value('retention_count', None)
            if keep not in (None, ''):
                cfg['retention_count'] = max(1, int(keep))
    except Exception:  # noqa: BLE001, S110
        pass
    return cfg


@shared_task(bind=True, time_limit=60 * 60, soft_time_limit=60 * 55)
def run_backup(self) -> dict:
    """Invoke `manage.py morph_backup`. Returns a small status dict."""
    cfg = _config()
    args: list[str] = []
    if not cfg['include_media']:
        args.append('--no-media')
    # The settings panel's directory and retention used to be ignored.
    if cfg['backup_dir']:
        args += ['--dest', cfg['backup_dir']]
    if cfg['retention_count']:
        args += ['--keep', str(cfg['retention_count'])]

    out = io.StringIO()
    try:
        call_command('morph_backup', *args, stdout=out, stderr=out)
        msg = out.getvalue().strip().splitlines()[-1] if out.getvalue() else ''
        logger.info('backups.run_backup: %s', msg)
        return {'ok': True, 'last_line': msg[:200]}
    except Exception as e:
        # A failed backup is a data-loss risk and must be LOUD — the old code
        # swallowed the exception and returned ok:False, so Celery saw success
        # and the nightly backup silently failed for the plugin's whole life
        # (the runtime image had no pg_dump). Surface it to the error log AND
        # re-raise so the task shows as FAILED in monitoring.
        logger.error('backups.run_backup failed: %s', e, exc_info=True)
        try:
            from core.errors.services import record_message

            record_message(
                f'Nightly backup failed: {e}',
                level='error',
                source='backups.run_backup',
                exception_class=type(e).__name__,
            )
        except Exception:  # noqa: BLE001 — observability write must not mask the original
            logger.error('backups.run_backup: could not record error event', exc_info=True)
        raise
