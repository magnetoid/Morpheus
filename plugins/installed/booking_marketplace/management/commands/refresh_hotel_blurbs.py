"""Rewrite the generated meta description on already-seeded hotels.

`seed_hotels_montenegro` is create-only (`_backfill_property` fills empty
fields but never clobbers), so the improved `_blurb_for` never reaches the
100 live hotels — this closes that gap, the same role `refresh_experience_copy`
plays for experiences.

The old `short_description` was tier + type + town only, so nine 4-star
Podgorica hotels shared 'An upscale hotel in Podgorica.' (18 collision groups,
52 hotels). Each is now led by the unique hotel name and names the hotel's real
amenities.

Only rows still holding the exact legacy string are rewritten — a host who
edited one keeps their words (the SeoMeta.auto_filled rule). Idempotent: a
second run matches nothing, because the new blurb is not the legacy string.

    python manage.py refresh_hotel_blurbs [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from plugins.installed.booking_marketplace.management.commands.seed_hotels_montenegro import (
    PTYPE_LABELS,
    _blurb_for,
    _legacy_short_blurb,
)
from plugins.installed.booking_marketplace.models import Property


class Command(BaseCommand):
    help = "Rewrite hotels' generated meta description (short_description) in place."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing.',
        )

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        rewritten = kept = 0
        changed: list[Property] = []
        for prop in Property.objects.all():
            label = PTYPE_LABELS.get(prop.property_type, 'Hotel')
            legacy = _legacy_short_blurb(prop.location, prop.star_rating, label)
            if prop.short_description != legacy:
                # host-edited, already refreshed, or an out-of-schema row — leave it
                kept += 1
                continue
            new_short = _blurb_for(
                prop.name, prop.location, prop.star_rating, label, prop.amenities
            )[0]
            if new_short == prop.short_description:
                kept += 1
                continue
            prop.short_description = new_short
            changed.append(prop)
            rewritten += 1
            if dry and rewritten <= 5:
                self.stdout.write(f'  {prop.name}: {new_short}')

        if not dry and changed:
            Property.objects.bulk_update(changed, ['short_description'])

        verb = 'would rewrite' if dry else 'rewrote'
        self.stdout.write(
            self.style.SUCCESS(f'{verb} {rewritten} hotel meta descriptions ({kept} left as-is).')
        )
