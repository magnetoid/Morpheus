"""`python manage.py safe_migrate`: migrate, backing the database up first.

The web container's entrypoint runs this in place of `migrate` on every boot
(scripts/docker-entrypoint.sh). With migrations pending it first backs the
database up into the pre-deploy folder, and a failed backup exits non-zero
before anything is migrated. After migrating it records the deploy as a
DeployEvent. The steps share one process on purpose: each `manage.py` start
costs about three seconds, and the store answers 503 while the web container
boots. See core/deploys.py.
"""

from __future__ import annotations

import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from core import deploys
from core.management.commands.morph_backup import Command as BackupCommand

logger = logging.getLogger('morpheus.deploys')


class Command(BaseCommand):
    help = 'Migrate, backing the database up first when there is anything to migrate.'
    requires_system_checks = []  # migrate runs them

    def handle(self, *args, **options):
        self._back_up_first()
        self._migrate()
        self._record()

    def _back_up_first(self) -> None:
        if deploys.read_handoff() is not None:
            # This container ran this step, then restarted (a crash loop). A second
            # backup now could copy a half-migrated database.
            self.stdout.write(
                '[safe_migrate] Backup step already done in this container; not repeated.'
            )
            return
        pending, fresh = deploys.migration_plan()
        backup = ''
        if not pending:
            self.stdout.write('[safe_migrate] No migrations to run, so no backup is needed.')
        elif fresh:
            self.stdout.write(
                f'[safe_migrate] New database: {len(pending)} migrations and nothing to back up.'
            )
        else:
            self.stdout.write(
                f'[safe_migrate] {len(pending)} migrations to run; backing up the database first.'
            )
            command = BackupCommand(stdout=self.stdout, stderr=self.stderr)
            try:
                call_command(
                    command,
                    dest=str(deploys.predeploy_dir()),
                    keep=deploys.BACKUP_KEEP,
                    no_media=True,
                    label=deploys.deploy_label(),
                )
            except Exception as exc:
                raise CommandError(
                    f'[safe_migrate] The backup failed, so nothing was migrated: {exc}'
                ) from exc
            backup = str(command.archive_path)
        deploys.write_handoff({'backup': backup, 'migrations': pending})

    def _migrate(self) -> None:
        # skip_checks=False: `manage.py migrate` ran the system checks on every boot.
        call_command('migrate', interactive=False, skip_checks=False)

    def _record(self) -> None:
        # The record feeds the Version & updates page; it never keeps the store down.
        try:
            event, created = deploys.record_deploy()
        except Exception:
            logger.exception('safe_migrate: could not record this deploy')
            self.stderr.write('[safe_migrate] Could not record this deploy; carrying on.')
            return
        if not created:
            self.stdout.write(f'[safe_migrate] {event.version} restarted; already recorded.')
            return
        commit = f' ({event.commit[:7]})' if event.commit else ''
        count = f', {len(event.migrations)} migrations applied' if event.migrations else ''
        self.stdout.write(f'[safe_migrate] Recorded {event.version}{commit}{count}.')
