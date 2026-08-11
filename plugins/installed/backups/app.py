"""Backups plugin.

Wraps the existing ``manage.py morph_backup`` management command in a
Celery beat task that runs once a day at 03:30 UTC. The command itself
already handles destination directory, retention pruning, and Postgres
or SQLite engines — see ``core.management.commands.morph_backup``.

Configuration is read from env (consumed by the underlying command):

    MORPHEUS_BACKUP_DIR  — default ``/tmp/morpheus-backups``
    MORPHEUS_BACKUP_KEEP — default ``7``
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel

try:
    from celery.schedules import crontab

    _DAILY = crontab(hour=3, minute=30)  # 03:30 UTC
except Exception:  # noqa: BLE001 — celery missing in management commands
    _DAILY = 60 * 60 * 24


class BackupsPlugin(Plugin):
    name = 'backups'
    label = 'Backups'
    version = '0.1.0'
    description = (
        'Daily database + media backup via the morph_backup management '
        'command, scheduled through Celery beat.'
    )
    has_models = False

    def ready(self) -> None:
        self.register_celery_tasks('plugins.installed.backups.tasks')
        self.register_celery_beat(
            'backups.daily',
            {
                'task': 'plugins.installed.backups.tasks.run_backup',
                'schedule': _DAILY,
            },
        )

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Backups',
            description='Daily database + media backup schedule and retention.',
            schema=self.get_config_schema(),
            category='developer',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'include_media': {
                    'type': 'boolean',
                    'title': 'Include media files',
                    'default': True,
                    'description': 'When off the task passes --no-media; useful when media is on S3 / a CDN.',
                },
                'backup_dir': {
                    'type': 'string',
                    'title': 'Backup directory',
                    'default': '/tmp/morpheus-backups',  # noqa: S108  # nosec B108
                    'description': 'Where dumps land. Reads MORPHEUS_BACKUP_DIR env var if this is blank.',
                },
                'retention_count': {
                    'type': 'integer',
                    'title': 'Keep N most-recent backups',
                    'default': 7,
                    'description': 'Older backups are pruned after each run.',
                },
                'schedule_hour_utc': {
                    'type': 'integer',
                    'title': 'Daily run hour (UTC)',
                    'default': 3,
                    'description': 'Hour of day the backup task fires. 0-23.',
                },
            },
        }
