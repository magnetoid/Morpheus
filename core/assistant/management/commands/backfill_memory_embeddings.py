"""Backfill semantic embeddings for LindaMemory rows that don't have one yet.

Idempotent: only embeds rows whose `embedding` is empty, unless `--all`, which
embeds every row again (after the store got an embeddings provider, the rows
kept from before still hold hash vectors, which match nothing by meaning).
Safe with no AI provider configured (hash vectors throughout). A row the
provider cannot embed right now is left for the next run.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core.assistant.models import LindaMemory
from core.embeddings import embed_comparable


class Command(BaseCommand):
    help = 'Compute embeddings for LindaMemory rows missing one (idempotent).'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--all', action='store_true', help='Embed every row again.')

    def handle(self, *args, **options):
        done = waiting = 0
        for row in LindaMemory.objects.all().iterator():
            if row.embedding and not options.get('all'):
                continue
            vector = embed_comparable(f'{row.key}: {row.value}')
            if not vector:
                waiting += 1
                continue
            row.embedding = vector
            row.save(update_fields=['embedding'])
            done += 1
        self.stdout.write(self.style.SUCCESS(f'Embedded {done} memory row(s).'))
        if waiting:
            self.stdout.write(f'{waiting} row(s) could not be embedded now; run this again.')
