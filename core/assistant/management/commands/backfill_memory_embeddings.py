"""Backfill semantic embeddings for LindaMemory rows that don't have one yet.

Idempotent: only embeds rows whose `embedding` is empty. Safe with no AI
provider configured (core.embeddings falls back to a deterministic hash).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core.assistant.models import LindaMemory
from core.embeddings import embed


class Command(BaseCommand):
    help = 'Compute embeddings for LindaMemory rows missing one (idempotent).'

    def handle(self, *args, **options):
        done = 0
        for row in LindaMemory.objects.all().iterator():
            if row.embedding:
                continue
            row.embedding = embed(f'{row.key}: {row.value}')
            row.save(update_fields=['embedding'])
            done += 1
        self.stdout.write(self.style.SUCCESS(f'Embedded {done} memory row(s).'))
