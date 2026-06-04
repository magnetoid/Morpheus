"""Regenerate the sitemap from the CLI / cron.

The sitemap is rendered live per request, so this recounts entries, purges the
CDN's cached copies of the sitemap URLs, and pings IndexNow so crawlers re-pull.
Thin wrapper over ``seo.services.regenerate_sitemap`` (the same code the
dashboard button and Linda call) so behaviour can't drift between surfaces.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from plugins.installed.seo.services import regenerate_sitemap


class Command(BaseCommand):
    help = 'Recount + purge CDN + ping crawlers for the sitemap.'

    def handle(self, *args, **options):
        res = regenerate_sitemap(triggered_by='cli')
        counts = res.get('counts') or {}
        self.stdout.write(
            self.style.SUCCESS(
                f'Sitemap regenerated: {counts.get("total", 0)} URLs '
                f'({counts.get("product_count", 0)} products, '
                f'{counts.get("book_facet_count", 0)} book facets, '
                f'{counts.get("page_count", 0)} pages). '
                f'{res.get("purged_zones", 0)} CDN zone(s) purged; '
                f'ping {"sent" if res.get("pinged") else "skipped"} '
                f'({res.get("ping_status") or "—"}).'
            )
        )
