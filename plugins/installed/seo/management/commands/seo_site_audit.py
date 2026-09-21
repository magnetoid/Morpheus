"""Crawl this store's own sitemap in-process and cache the findings.

    python manage.py seo_site_audit            # every URL in the sitemap
    python manage.py seo_site_audit --limit 50 # a quick sample

The dashboard's SEO page reads the cached result; it never crawls itself,
because a full render per URL inside a live request would re-enter the
middleware stack and tie up a worker for the length of the catalogue.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Audit every URL in the store's sitemap and cache the findings."

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Only check the first N URLs (0 = the whole sitemap).',
        )

    def handle(self, *args, **options):
        from plugins.installed.seo.services.site_audit import run_and_store

        limit = options['limit'] or None
        report = run_and_store(limit=limit)

        self.stdout.write(
            f'Checked {report["pages_checked"]} URL(s) — score {report["score"]}/100.'
        )
        for finding in report['findings']:
            style = (
                self.style.ERROR
                if finding['severity'] == 'critical'
                else self.style.WARNING
                if finding['severity'] == 'warning'
                else self.style.NOTICE
            )
            self.stdout.write(
                style(f'  [{finding["severity"]:8}] {finding["count"]:4} {finding["title"]}')
            )
        if not report['findings']:
            self.stdout.write(self.style.SUCCESS('  No findings.'))
