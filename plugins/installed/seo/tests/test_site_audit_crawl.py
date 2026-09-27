"""The nightly site audit must see the store, not its own rate limiter.

It crawls every sitemap URL in-process as an anonymous 127.0.0.1 client, which
the storefront rate limiter counts like any visitor: past 300 fast pages a
minute every remaining URL came back 429 (439 of supernatural's 1,334 audited
pages), and the score was computed over those. And `_facts` caught every
exception per page — Celery's SoftTimeLimitExceeded included — so the crawl ran
on until the hard limit SIGKILLed the worker: dotbooks' 3,748-URL audit never
finished once.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from celery.exceptions import SoftTimeLimitExceeded
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.seo.services import site_audit


class SiteAuditCrawlTests(TestCase):
    def setUp(self):
        for i in range(4):
            Product.objects.create(
                name=f'Audit Probe {i}',
                slug=f'audit-probe-{i}',
                sku=f'AP-{i}',
                price=Money(Decimal('5.00'), 'USD'),
                status='active',
            )

    @override_settings(MORPHEUS_RATELIMIT_ENABLED=True, MORPHEUS_RATELIMIT_PER_MINUTE=2)
    def test_the_audit_is_not_throttled_by_the_store_it_audits(self):
        from django.core.cache import cache

        cache.clear()
        report = site_audit.collect(limit=6)
        self.assertGreaterEqual(report['pages_checked'], 5)
        errors = [
            example
            for finding in report['findings']
            if finding['code'] == 'sitemap_error'
            for example in finding['examples']
        ]
        self.assertFalse([e for e in errors if e.endswith('429')], errors)

    @override_settings(MORPHEUS_RATELIMIT_ENABLED=True, MORPHEUS_RATELIMIT_PER_MINUTE=2)
    def test_a_real_visitor_is_still_rate_limited(self):
        from django.core.cache import cache

        cache.clear()
        codes = [self.client.get('/').status_code for _ in range(4)]
        self.assertIn(429, codes)

    def test_the_soft_time_limit_ends_the_crawl_with_a_partial_report(self):
        real_facts = site_audit._facts
        calls = {'n': 0}

        def facts(client, path, host):
            calls['n'] += 1
            if calls['n'] == 3:
                raise SoftTimeLimitExceeded()
            return real_facts(client, path, host)

        with patch.object(site_audit, '_facts', side_effect=facts):
            report = site_audit.collect(limit=6)

        self.assertEqual(calls['n'], 3, 'the crawl kept going after the soft limit')
        self.assertEqual(report['pages_checked'], 2)
        self.assertTrue(report['partial'])
