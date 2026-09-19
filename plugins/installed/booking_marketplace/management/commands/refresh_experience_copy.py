"""Apply the data-module copy (names/descriptions) to existing rows by slug.

Idempotent content refresh: seeds are create-only, so copy improvements in
_experiences_data.py never reach already-seeded rows — this command closes
that gap. Safe to re-run.

    python manage.py refresh_experience_copy
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from plugins.installed.booking_marketplace.management.commands._experiences_data import (
    LEGACY_COPY,
    NEW_EXPERIENCES,
)
from plugins.installed.booking_marketplace.models import BookableService


class Command(BaseCommand):
    help = 'Refresh experience copy (name/short_description/description) from the data modules.'

    def handle(self, *args, **opts):
        updated = 0
        copy_by_slug = {e['slug']: e for e in NEW_EXPERIENCES}
        copy_by_slug.update(LEGACY_COPY)
        for slug, c in copy_by_slug.items():
            updated += BookableService.objects.filter(slug=slug).update(
                name=c['name'],
                short_description=c['short_description'],
                description=c['description'],
            )
        self.stdout.write(f'Copy refreshed on {updated} experiences.')
