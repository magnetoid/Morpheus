"""Export the EU AI Act evidence report from the CLI.

    manage.py export_ai_act_report --days 90 --format csv > evidence.csv
    manage.py export_ai_act_report --format json

Reuses agent_core.compliance.build_ai_act_report so the CLI and the dashboard
page never drift.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from plugins.installed.agent_core.compliance import build_ai_act_report


class Command(BaseCommand):
    help = 'Export the EU AI Act evidence report (automated decisions + approvals).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90, help='Window size (default 90).')
        parser.add_argument('--format', choices=['csv', 'json'], default='csv')

    def handle(self, *args, **opts):
        days = max(1, min(3650, int(opts['days'])))
        until = timezone.now()
        since = until - timedelta(days=days)
        report = build_ai_act_report(since=since, until=until)

        if opts['format'] == 'json':
            self.stdout.write(json.dumps(report, indent=2, default=str))
            return

        w = csv.writer(self.stdout)
        w.writerow(['section', 'timestamp', 'agent_or_tool', 'target_or_state', 'model', 'actor'])
        for d in report['decisions']:
            w.writerow(['decision', d['timestamp'], d['tool'], d['target'], d['model'], d['actor']])
        for a in report['approvals']:
            w.writerow(['approval', a['timestamp'], a['tool'], a['state'], '', a['decided_by']])
        for c in report['consents']:
            w.writerow([c['kind'], c['timestamp'], c['tool'], c['outcome'], '', c['actor']])
        # Summary to stderr so it doesn't pollute a piped CSV.
        s = report['summary']
        sys.stderr.write(
            f'\n{s["total_decisions"]} decisions, {s["total_approvals"]} approvals '
            f'over {days} days.\n'
        )
