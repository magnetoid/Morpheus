"""Re-send the double opt-in email to subscribers still waiting to confirm.

Until v0.75.17 the Celery worker never registered the email task, so every
confirmation email queued from 2026-07-12 on was discarded: those subscribers
asked to subscribe, never got the link, and sit at `pending` forever.

    python manage.py newsletter_resend_confirmations [--since YYYY-MM-DD] [--dry-run]

Each pending subscriber gets the ordinary confirmation (the same path a
re-subscribe takes). Addresses that cannot receive mail are skipped.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.utils.dateparse import parse_date


def _mask(email: str) -> str:
    local, _, domain = email.partition('@')
    return f'{local[:2]}***@{domain}'


class Command(BaseCommand):
    help = 'Re-send the confirmation email to pending newsletter subscribers.'

    def add_arguments(self, parser):
        parser.add_argument('--since', help='Only subscribers who signed up on/after YYYY-MM-DD.')
        parser.add_argument('--dry-run', action='store_true', help='List, send nothing.')

    def handle(self, *args, **options):
        from plugins.installed.newsletter.models import NewsletterSubscriber
        from plugins.installed.newsletter.services import subscribe

        pending = NewsletterSubscriber.objects.filter(status='pending').order_by('created_at')
        if options['since']:
            since = parse_date(options['since'])
            if since is None:
                raise CommandError('--since must be YYYY-MM-DD')
            pending = pending.filter(created_at__date__gte=since)

        dry_run = options['dry_run']
        sent = skipped = 0
        for sub in pending:
            try:
                validate_email(sub.email)
            except ValidationError:
                skipped += 1
                self.stdout.write(f'  skip (not a deliverable address): {_mask(sub.email)}')
                continue
            if not dry_run:
                subscribe(sub.email, source=sub.source, customer=sub.customer)
            sent += 1
            self.stdout.write(f'  {"would send" if dry_run else "sent"}: {_mask(sub.email)}')
        verb = 'Would re-send' if dry_run else 'Re-sent'
        self.stdout.write(f'{verb} {sent} confirmation(s); skipped {skipped}.')
