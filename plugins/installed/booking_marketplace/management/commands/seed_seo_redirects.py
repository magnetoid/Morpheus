"""Seed the SEO 301 redirects for URLs the July 2026 SEO audit found returning
404 (old indexed paths that lost their target when the store was rebuilt).
Idempotent — updates the target if the row already exists. The /en/* prefix is
handled at the URL layer (booking_marketplace/urls.py), not here.

    python manage.py seed_seo_redirects
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

# (from_path, to_path) — all permanent 301, exact-path (SeoRedirectMiddleware
# matches from_path exactly and fires on 404).
REDIRECTS = [
    ('/blog/', '/journal/'),
    ('/blog', '/journal/'),
    # Articles lost in the rebuild — send link equity to the journal index
    # rather than leave a hard 404 (no recovered body to republish).
    ('/boat-fishing-in-kotor', '/journal/'),
    # Recovered + republished (seed_journal_serbian) at its original slug.
    ('/manastiri-crne-gore-vodic', '/journal/manastiri-crne-gore-vodic/'),
    ('/privacy-policy-2', '/p/privacy/'),
]


class Command(BaseCommand):
    help = 'Seed SEO 301 redirects for the audited 404 URLs (idempotent).'

    def handle(self, *args, **options):
        from plugins.installed.seo.models import Redirect

        created = updated = 0
        for from_path, to_path in REDIRECTS:
            _, was_created = Redirect.objects.update_or_create(
                from_path=from_path,
                defaults={'to_path': to_path, 'status_code': 301, 'is_active': True},
            )
            created += int(was_created)
            updated += int(not was_created)
        self.stdout.write(
            self.style.SUCCESS(f'SEO redirects: {created} created, {updated} updated.')
        )
