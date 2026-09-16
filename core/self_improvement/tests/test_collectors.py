"""Collector tests.

error_log regression (July 2026 audit): the collector read the RETIRED
`observability.ErrorEvent`, which nothing writes anymore (ADR 0025 moved the
write path to `core.errors.ErrorEvent`), so it silently ingested an empty
table. It now reads `core.errors.ErrorEvent` with the matching field names.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from core.errors.models import ErrorEvent
from core.self_improvement.collectors import zero_search
from core.self_improvement.collectors.error_log import ErrorLogCollector
from core.self_improvement.collectors.seo_gap import SeoGapCollector
from core.self_improvement.models import SiSignal
from core.self_improvement.services import fingerprint_for
from plugins.installed.cms.models import Page


class ErrorLogCollectorTests(TestCase):
    def test_reads_core_errors_and_maps_fields(self) -> None:
        ev = ErrorEvent.objects.create(
            kind='server',
            level='error',
            fingerprint='abc123',
            exception_class='KeyError',
            message="KeyError: 'seo_meta'",
            traceback='Traceback...\n  File "/app/plugins/x.py", line 9, in view\n    ...',
            path='/checkout/pay/',
        )

        signals = list(ErrorLogCollector().run())
        self.assertEqual(len(signals), 1)
        sig = signals[0]
        self.assertEqual(sig.source, 'error_log')
        # Fingerprint namespaces the model's own stable hash under SOURCE.
        self.assertEqual(sig.fingerprint, fingerprint_for('error_log', 'abc123'))
        self.assertEqual(sig.payload['exception_class'], 'KeyError')
        self.assertEqual(sig.payload['kind'], 'server')
        self.assertEqual(sig.payload['path'], '/checkout/pay/')
        self.assertEqual(sig.occurred_at, ev.created_at)
        # A checkout/payment path is a critical path → bumped severity.
        self.assertEqual(sig.severity, 85)

    def test_client_js_error_is_advisory_severity(self) -> None:
        ErrorEvent.objects.create(
            kind='client',
            level='error',
            fingerprint='js1',
            exception_class='TypeError',
            message='TypeError: undefined',
            path='/products/',
        )
        signals = list(ErrorLogCollector().run())
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].severity, 30)

    def test_no_events_yields_nothing(self) -> None:
        self.assertEqual(list(ErrorLogCollector().run()), [])


class ZeroSearchRateCapTests(TestCase):
    """The zero_search handler runs synchronously on the public /products/?q=
    path; a flood of unique junk queries must not mint unbounded SiSignal rows
    (pre-deploy review finding, 2026-07)."""

    def setUp(self) -> None:
        cache.clear()

    def test_floods_are_capped_per_hour(self) -> None:
        with patch.object(zero_search, '_HOURLY_CAP', 3):
            for i in range(6):
                zero_search.on_search_performed(query=f'nonexistent-{i}', result_count=0)
        # Only the first 3 misses are written; the rest are dropped at the cache.
        self.assertEqual(SiSignal.objects.filter(source='zero_search').count(), 3)

    def test_hit_never_emits(self) -> None:
        zero_search.on_search_performed(query='dune', result_count=5)
        self.assertEqual(SiSignal.objects.filter(source='zero_search').count(), 0)


class SeoGapCollectorTests(TestCase):
    """seo_gap regressions (2026-09).

    1. The collector filtered `cms.Page` on a `meta_description` column the
       model has never had, so `scan_seo_daily` raised FieldError on EVERY
       run from 2026-06-01 (107 of 107 failed live) and the page gap class
       was never collected. Nothing had ever called `run()`.
    2. It reported a blank `Product.og_title` as debt, but `og:title` falls
       back to the page title — 648 of 861 live products carried a signal no
       healer can repair.
    3. It read only the native description column, ignoring the `SeoMeta`
       overlay that wins at render.
    """

    def _product(self, **kw):
        from plugins.installed.catalog.models import Product

        defaults = {
            'name': 'Book',
            'slug': 'book',
            'sku': 'BOOK1',
            'price': Money(Decimal('5.00'), 'USD'),
            'product_type': 'simple',
            'status': 'active',
        }
        return Product.objects.create(**{**defaults, **kw})

    def _overlay(self, obj, description):
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.seo.models import SeoMeta

        # update_or_create, not create: `autofill_meta_for` already mints a
        # SeoMeta row for every product, and the pair is unique.
        row, _ = SeoMeta.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(obj.__class__),
            object_id=str(obj.pk),
            defaults={'description': description},
        )
        return row

    def _gaps(self):
        return [s.payload['gap'] for s in SeoGapCollector().run()]

    def test_run_completes_over_every_gap_class(self) -> None:
        """The crash: one bad column killed the run after it had already
        emitted signals, so the job recorded `failed` every night."""
        Page.objects.create(slug='about', title='About', excerpt='')
        self.assertIn('cms_page_meta_description', self._gaps())

    def test_page_with_an_excerpt_is_not_a_gap(self) -> None:
        # A page's description resolves from `excerpt` when the overlay is
        # empty (seo/pages/resolve.py:_description_from_object).
        Page.objects.create(slug='about', title='About', excerpt='What we do.')
        self.assertNotIn('cms_page_meta_description', self._gaps())

    def test_page_described_only_by_the_overlay_is_not_a_gap(self) -> None:
        page = Page.objects.create(slug='about', title='About', excerpt='')
        self._overlay(page, 'What we do.')
        self.assertNotIn('cms_page_meta_description', self._gaps())

    def test_product_without_a_description_anywhere_is_a_gap(self) -> None:
        self._product(meta_description='')
        self.assertIn('product_meta_description', self._gaps())

    def test_product_described_only_by_the_overlay_is_not_a_gap(self) -> None:
        product = self._product(meta_description='')
        self._overlay(product, 'A very good book.')
        self.assertNotIn('product_meta_description', self._gaps())

    def test_blank_og_title_is_not_reported(self) -> None:
        # og:title renders from the title when blank — seo/services/_helpers.py:
        # `og_title = self.og_title or self.title`. Reporting it was 648 rows
        # of permanent, unhealable debt on the live store.
        self._product(meta_description='Set.', og_title='')
        self.assertEqual(self._gaps(), [])

    def test_image_without_alt_text_is_a_gap(self) -> None:
        from plugins.installed.catalog.models import ProductImage

        product = self._product(meta_description='Set.')
        ProductImage.objects.create(product=product, image='products/x.jpg', alt_text='')
        self.assertIn('product_image_alt', self._gaps())
