"""Write listing content from a JSON file, backing up what it replaces first."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Write content (names, texts, SEO, highlights, itinerary, guest questions) to listings '
        'and their products. The backup holds the current values in the same shape: apply it '
        'to restore them.'
    )

    def add_arguments(self, parser):
        parser.add_argument('file', help='JSON mapping a listing slug to its fields')
        parser.add_argument('--backup', help='Where to write the current values first')
        parser.add_argument('--dry-run', action='store_true', help='Validate and report only')

    def handle(self, *args, **options):
        from plugins.installed.booking_marketplace import content

        path = options['file']
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError(f'Cannot read {path}: {exc}') from exc
        problems = content.validate(data)
        if problems:
            raise CommandError(
                f'{len(problems)} problem(s), nothing written:\n' + '\n'.join(problems)
            )
        snapshot = content.snapshot(data)
        unrestorable = content.validate(snapshot)
        if unrestorable:  # a backup that cannot go back in is no backup
            raise CommandError(
                'The backup would not restore, nothing written; fix these listings first:\n'
                + '\n'.join(unrestorable)
            )
        if options['dry_run']:
            self.stdout.write(f'would write {len(data)} listing(s)')
            return
        backup = options['backup']
        if not backup:
            raise CommandError('--backup <file> is required for a real run (or use --dry-run)')
        try:
            with open(backup, 'x', encoding='utf-8') as fh:  # never over an earlier backup
                fh.write(json.dumps(snapshot, ensure_ascii=False, indent=1))
        except FileExistsError as exc:
            raise CommandError(
                f'The backup {backup} already exists; name a new file so the first is kept'
            ) from exc
        except OSError as exc:
            raise CommandError(f'Cannot write the backup {backup}: {exc}') from exc
        written = content.apply(data)
        self.stdout.write(f'written={written} backup={backup}')
