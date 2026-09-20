"""Set the store + SEO brand name to STORE_NAME (idempotent).

Fixes the leftover "dot books" / "Morpheus Store" brand that the SEO brand_name()
falls back to when no StoreSettings / SiteSeoSettings rows carry the real name.
Runs on deploy via the entrypoint.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Set store + SEO brand name to STORE_NAME (idempotent).'

    def handle(self, *args, **options):
        name = (getattr(settings, 'STORE_NAME', '') or 'Montenegro Experience').strip()

        # core.StoreSettings (singleton)
        try:
            from core.models import StoreSettings

            ss = StoreSettings.objects.first()
            if ss is None:
                ss = StoreSettings(store_name=name)
                ss.save()
                self.stdout.write(f'StoreSettings created: store_name={name!r}')
            elif ss.store_name != name:
                ss.store_name = name
                ss.save(update_fields=['store_name'])
                self.stdout.write(f'StoreSettings updated: store_name={name!r}')
            else:
                self.stdout.write(f'StoreSettings ok: store_name={name!r}')
        except Exception as e:  # pragma: no cover
            self.stdout.write(f'StoreSettings skipped: {e}')

        # seo.SiteSeoSettings (singleton)
        try:
            from plugins.installed.seo.models import SiteSeoSettings

            so = SiteSeoSettings.objects.first()
            if so is None:
                so = SiteSeoSettings(organization_name=name)
                so.save()
                self.stdout.write(f'SiteSeoSettings created: organization_name={name!r}')
            elif so.organization_name != name:
                so.organization_name = name
                so.save(update_fields=['organization_name'])
                self.stdout.write(f'SiteSeoSettings updated: organization_name={name!r}')
            else:
                self.stdout.write(f'SiteSeoSettings ok: organization_name={name!r}')
        except Exception as e:  # pragma: no cover
            self.stdout.write(f'SiteSeoSettings skipped: {e}')
