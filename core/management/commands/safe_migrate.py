"""`python manage.py safe_migrate`: migrate, backing the database up first.

The web container's entrypoint runs this in place of `migrate` on every boot
(scripts/docker-entrypoint.sh). With migrations pending it first backs the
database up into the pre-deploy folder, and a failed backup records the attempt
and exits non-zero before anything is migrated. It records the deploy as a
DeployEvent before migrating (after, when DeployEvent itself is being
migrated), then migrates, and on a rollback emails the operators last. The
steps share one process on purpose: each `manage.py` start costs about three
seconds, and the store answers 503 while the web container boots. See
core/deploys.py.
"""

from __future__ import annotations

import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core import deploys
from core.management.commands.morph_backup import Command as BackupCommand

logger = logging.getLogger('morpheus.deploys')


class Command(BaseCommand):
    help = 'Migrate, backing the database up first when there is anything to migrate.'
    requires_system_checks = []  # migrate runs them

    def handle(self, *args, **options):
        self._rollback = None
        self._back_up_first()
        # Before migrating, so a migration that crashes still leaves the attempt
        # and its backup on record for the rollback notice.
        recorded = self._record(final=False)
        self._migrate()
        if not recorded:
            self._record(final=True)
        deploys.clear_handoff()
        self._tell_rollback()

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
                # On record, so the release the store is put back on says why.
                deploys.record_failed_attempt(pending)
                raise CommandError(
                    f'[safe_migrate] The backup failed, so nothing was migrated: {exc}'
                ) from exc
            backup = str(command.archive_path)
        deploys.write_handoff({'backup': backup, 'migrations': pending})

    def _migrate(self) -> None:
        # skip_checks=False: `manage.py migrate` ran the system checks on every boot.
        call_command('migrate', interactive=False, skip_checks=False)

    def _record(self, *, final: bool) -> bool:
        """Record this deploy; False when it cannot be written yet. Before
        migrating, the table or one of its columns can still be missing (a new
        database, or a deploy that migrates DeployEvent itself): then it is
        written after migrating. The record never keeps the store down."""
        try:
            with transaction.atomic():
                event, created = deploys.record_deploy()
        except Exception:
            if not final:
                return False
            logger.exception('safe_migrate: could not record this deploy')
            self.stderr.write('[safe_migrate] Could not record this deploy; carrying on.')
            return True
        if not created:
            self.stdout.write(f'[safe_migrate] {event.version} restarted; already recorded.')
            return True
        commit = f' ({event.commit[:7]})' if event.commit else ''
        count = f', {len(event.migrations)} migrations' if event.migrations else ''
        self.stdout.write(f'[safe_migrate] Recorded {event.version}{commit}{count}.')
        if event.rolled_back_from:
            self._rollback = event
        return True

    def _tell_rollback(self) -> None:
        """Email the operators that the store went back to an older release. Last,
        and fail-soft: the email must never stop or slow the boot that brings the
        store back."""
        event = self._rollback
        if event is None:
            return
        try:
            told = deploys.notify_rollback(event)
        except Exception:
            logger.exception('safe_migrate: could not send the rollback email')
            told = False
        self.stdout.write(
            f'[safe_migrate] Back on {event.version} after {event.rolled_back_from}: '
            + ('told the operators.' if told else 'could not email the operators.')
        )
