"""Prune old ErrorEvent rows.

Default retention: 30 days. Run on a daily cron (Celery Beat, systemd
timer, or a Coolify schedule) so the table doesn't grow unbounded on a
high-traffic site.

Usage:
    python manage.py prune_errors                  # delete rows older than 30 days
    python manage.py prune_errors --keep-days 90
    python manage.py prune_errors --dry-run
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Delete ErrorEvent rows older than --keep-days (default 30).'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--keep-days',
            type=int,
            default=30,
            help='Rows older than this many days are deleted (default: 30).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Count what would be deleted; do not actually delete.',
        )

    def handle(self, *args, **opts) -> None:
        from core.errors.models import ErrorEvent

        keep_days = int(opts['keep_days'])
        cutoff = timezone.now() - timedelta(days=keep_days)
        qs = ErrorEvent.objects.filter(created_at__lt=cutoff)
        count = qs.count()

        if opts['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f'dry-run — would delete {count} row(s) older than {cutoff:%Y-%m-%d %H:%M}'
                )
            )
            return

        if not count:
            self.stdout.write(f'nothing to prune (cutoff: {cutoff:%Y-%m-%d %H:%M})')
            return

        deleted, _ = qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f'pruned {deleted} row(s) older than {cutoff:%Y-%m-%d %H:%M} '
                f'(--keep-days {keep_days})'
            )
        )
