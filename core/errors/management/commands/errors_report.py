"""Print the error report for Claude Code, or mark a group resolved.

    python manage.py errors_report                 # Markdown, open groups, last 7 days
    python manage.py errors_report --days 30 --json
    python manage.py errors_report --fingerprint <fp>
    python manage.py errors_report --resolve <fp> [--note "fixed in v0.98.1"]

Claude Code with shell access runs it in a store's web container
(`docker exec <web> python manage.py errors_report`) and gets the same report
as "Copy for Claude Code" on the error log page.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Print the open error groups as a Markdown report for Claude Code, or resolve one.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Window in days (1 to 90).')
        parser.add_argument('--limit', type=int, default=50, help='Most groups to include.')
        parser.add_argument('--json', action='store_true', help='Print JSON instead of Markdown.')
        parser.add_argument(
            '--include-resolved', action='store_true', help='Include resolved groups too.'
        )
        parser.add_argument('--fingerprint', default='', help='Report one group, of any age.')
        parser.add_argument('--resolve', default='', help='Mark this fingerprint resolved.')
        parser.add_argument('--note', default='', help='Note to keep with --resolve.')

    def handle(self, *args, **opts):
        from core.errors.report import build_report, render_markdown, resolve

        if opts['resolve']:
            if not resolve(opts['resolve'], note=opts['note']):
                raise CommandError(f'No error has the fingerprint {opts["resolve"]}.')
            self.stdout.write(f'Resolved {opts["resolve"]}. It opens again if the error returns.')
            return
        report = build_report(
            days=opts['days'],
            include_resolved=opts['include_resolved'],
            limit=opts['limit'],
            fingerprint=opts['fingerprint'],
        )
        if opts['json']:
            self.stdout.write(json.dumps(report, indent=2, default=str))
        else:
            self.stdout.write(render_markdown(report))
