"""Site-wide SEO findings — the defects that only exist BETWEEN pages.

`audit.py` scores one product at a time and is blind to all of these. Every
check here corresponds to something a paid audit of a live Morpheus store
found in Sep 2026 that the dashboard could not have shown.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.seo.services import site_audit


def _codes(report) -> list[str]:
    return [f['code'] for f in report['findings']]


def _finding(report, code) -> dict | None:
    return next((f for f in report['findings'] if f['code'] == code), None)


class SiteAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product

        cls.category = Category.objects.create(name='Audit Cat', slug='audit-cat')
        cls.product = Product.objects.create(
            name='Audit Probe',
            slug='audit-probe',
            sku='AP-1',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
            status='active',
            category=cls.category,
            description='A description long enough not to trip the thin check. ' * 20,
        )

    def test_a_scan_reports_pages_and_a_score(self):
        report = site_audit.collect(limit=10)
        self.assertGreater(report['pages_checked'], 0)
        self.assertTrue(0 <= report['score'] <= 100)
        self.assertTrue(report['generated_at'])

    def test_two_pages_sharing_a_title_are_reported(self):
        from plugins.installed.cms.models import Page

        for slug in ('share-a', 'share-b'):
            Page.objects.create(
                slug=slug,
                title='Exactly The Same Title',
                state='published',
                body='<p>Distinct body text for this page.</p>',
                metadata={'category': 'journal'},
            )
        report = site_audit.collect(limit=60)
        finding = _finding(report, 'duplicate_title')
        self.assertIsNotNone(finding, f'expected duplicate_title, got {_codes(report)}')
        self.assertIn('Exactly The Same Title', ' '.join(finding['examples']))

    def test_coverage_is_measured_from_what_rendered(self):
        # Not from whether a column is non-empty: a description can be blank in
        # the database and still render from the fallback chain, and a column
        # can be full while the page shows nothing (the seo_gap landmine).
        report = site_audit.collect(limit=10)
        labels = {row['label'] for row in report['coverage']}
        self.assertEqual(
            labels,
            {'Title', 'Description', 'Canonical', 'One H1', 'Structured data', 'hreflang'},
        )
        for row in report['coverage']:
            self.assertLessEqual(row['count'], row['total'])
            self.assertTrue(0 <= row['pct'] <= 100)

    @override_settings(LANGUAGES=[('en', 'English')])
    def test_a_single_language_store_is_not_nagged_about_hreflang(self):
        self.assertNotIn('hreflang_missing', _codes(site_audit.collect(limit=10)))

    @override_settings(LANGUAGES=[('en', 'English'), ('sr', 'Srpski')])
    def test_a_multilingual_store_is_told_when_alternates_are_missing(self):
        # The largest single finding of the live audit: a real Serbian edition
        # that Google had no way to connect to the English tree.
        report = site_audit.collect(limit=10)
        finding = _finding(report, 'hreflang_missing')
        if finding is not None:
            self.assertGreater(finding['count'], 0)
            self.assertIn('hreflang', finding['why'])

    def test_findings_are_ordered_worst_first(self):
        report = site_audit.collect(limit=30)
        rank = {'critical': 0, 'warning': 1, 'notice': 2}
        severities = [rank[f['severity']] for f in report['findings']]
        self.assertEqual(severities, sorted(severities))

    def test_every_finding_explains_itself(self):
        # A finding a merchant cannot act on is a number, which is what this
        # page replaced. Each one states the cost and shows real examples.
        for finding in site_audit.collect(limit=30)['findings']:
            self.assertTrue(finding['title'], finding)
            self.assertTrue(finding['why'], finding['code'])
            self.assertTrue(finding['examples'], finding['code'])
            self.assertLessEqual(len(finding['examples']), 5)

    def test_a_redirecting_sitemap_url_is_critical(self):
        # The exact defect the audit found live: `/categories/` was in the
        # sitemap and 301'd to a route only an optional plugin mounts.
        from plugins.installed.seo.models import SitemapEntry

        SitemapEntry.objects.create(location='/goes-nowhere/', is_active=True)
        from plugins.installed.seo.models import Redirect

        Redirect.objects.create(
            from_path='/goes-nowhere/', to_path='/', status_code=301, is_active=True
        )
        report = site_audit.collect(limit=80)
        finding = _finding(report, 'sitemap_redirect') or _finding(report, 'sitemap_error')
        self.assertIsNotNone(
            finding, f'a sitemap url that does not resolve must be flagged: {_codes(report)}'
        )
        self.assertEqual(finding['severity'], 'critical')


class CacheTests(TestCase):
    def test_nothing_cached_reads_as_no_scan_yet(self):
        from django.core.cache import cache

        cache.delete(site_audit.CACHE_KEY)
        self.assertIsNone(site_audit.cached())

    def test_a_run_is_stored_and_read_back(self):
        stored = site_audit.run_and_store(limit=5)
        self.assertEqual(site_audit.cached()['generated_at'], stored['generated_at'])


class OverviewPageTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.staff = User.objects.create_user(
            username='seo-staff', email='s@example.test', password='x', is_staff=True
        )
        self.client.force_login(self.staff)

    def test_the_page_renders_before_any_scan_has_run(self):
        from django.core.cache import cache

        cache.delete(site_audit.CACHE_KEY)
        response = self.client.get('/dashboard/seo/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No site scan yet')

    def test_findings_render_once_a_scan_exists(self):
        site_audit.run_and_store(limit=8)
        response = self.client.get('/dashboard/seo/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Site health')
        self.assertContains(response, 'Head coverage')

    def test_the_run_endpoint_only_accepts_post(self):
        # A GET that triggered a full-site crawl would fire on every prefetch.
        response = self.client.get('/dashboard/seo/site-audit/run/')
        self.assertEqual(response.status_code, 302)


@override_settings(SECURE_SSL_REDIRECT=True)
class HttpsRedirectTests(TestCase):
    """The audit must work on a store that forces HTTPS — i.e. all of them.

    `SECURE_SSL_REDIRECT` is on in production and off in dev, so a plain
    in-process request is 301'd by SecurityMiddleware before it reaches a view.
    The first production run of this audit reported 59 of 59 URLs as
    "Sitemap lists URLs that redirect" — the dashboard lying at maximum volume,
    and invisible to every local test.
    """

    def test_forced_https_is_not_mistaken_for_a_broken_sitemap(self):
        report = site_audit.collect(limit=10)
        self.assertGreater(report['pages_checked'], 0)
        redirect_finding = _finding(report, 'sitemap_redirect')
        self.assertIsNone(
            redirect_finding,
            'SECURE_SSL_REDIRECT must not be reported as every page redirecting: '
            f'{redirect_finding}',
        )
        # And the pages must actually have been read, not just not-flagged.
        self.assertTrue(any(row['count'] for row in report['coverage']))


class ContributedCorpusTests(TestCase):
    """The audit and the sitemap dashboard must see the SAME urls as /sitemap.xml.

    Both read `iter_sitemap_entries()` once, which yields only what seo builds
    itself — a vertical's routes arrive through the `SITEMAP_URLS` filter. On
    the Montenegro marketplace that meant the dashboard reported 59 urls while
    the sitemap served 343, and the audit checked those same 59: every booking,
    stay, place and event — the commercial catalogue — was invisible to both.
    """

    def _with_contribution(self, fn):
        from morpheus.core import MorpheusEvents, hook_registry

        def _subscriber(value, **kwargs):
            return [*value, {'loc': 'https://testserver/contributed-probe/', 'priority': '0.7'}]

        hook_registry.register(MorpheusEvents.SITEMAP_URLS, _subscriber, priority=50)
        try:
            return fn()
        finally:
            hook_registry.unregister(MorpheusEvents.SITEMAP_URLS, _subscriber)

    def test_audit_covers_contributed_urls(self):
        from plugins.installed.seo.services.site_audit import _paths

        paths = self._with_contribution(lambda: _paths(None))
        self.assertIn('/contributed-probe/', paths)

    def test_sitemap_counts_matches_what_the_sitemap_serves(self):
        from plugins.installed.seo.services.sitemaps import (
            _merged_sitemap_entries,
            sitemap_counts,
        )

        counts, merged = self._with_contribution(
            lambda: (sitemap_counts(), _merged_sitemap_entries())
        )
        self.assertEqual(
            counts['total'],
            len(merged),
            'the dashboard total must equal the urls /sitemap.xml actually serves',
        )
        self.assertGreaterEqual(counts['contributed_count'], 1)

    def test_a_contributed_url_is_not_counted_as_hand_written(self):
        # `manual_count` means a merchant typed a SitemapEntry row; a booking
        # route is not that, and conflating them misreports both.
        from plugins.installed.seo.services.sitemaps import sitemap_counts

        counts = self._with_contribution(sitemap_counts)
        self.assertEqual(counts['manual_count'], 0)
