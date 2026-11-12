"""What the seo app tells crawlers and answer engines, checked against what is true.

The audit of 2026-11-12 found the `{site_name}` template token empty on every
store (it read a field the model does not have), the markdown export's reviews
query failing every time on another missing field, every product "in stock"
there, llms.txt listing switched-off categories under a heading it opened
before any row, a travel store's file titled "Morpheus store" and pointing at
its empty /products/ page, and IndexNow pinging drafts and booked services.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Product


def _product(**kw):
    defaults = {
        'name': 'Lantern',
        'slug': 'tc-lantern',
        'sku': 'TC-1',
        'status': 'active',
        'price': Money(Decimal('20.00'), 'EUR'),
    }
    defaults.update(kw)
    return Product.objects.create(**defaults)


class SiteNameTokenTests(TestCase):
    def test_the_token_names_the_organisation(self):
        from plugins.installed.seo.models import SiteSeoSettings
        from plugins.installed.seo.services.templating import render_template

        SiteSeoSettings.objects.create(organization_name='Lantern House')
        self.assertEqual(
            render_template('{name} at {site_name}', _product()), 'Lantern at Lantern House'
        )

    def test_the_store_name_stands_in(self):
        from core.models import StoreSettings
        from plugins.installed.seo.services.templating import render_template

        StoreSettings.objects.create(store_name='Kotor Lights')
        self.assertIn('Kotor Lights', render_template('{site_name}', _product()))


class MarkdownExportTests(TestCase):
    def test_approved_reviews_are_listed_and_pending_ones_are_not(self):
        from django.contrib.auth import get_user_model

        from plugins.installed.catalog.models import Review
        from plugins.installed.seo.services.ai_feeds import render_product_markdown

        product = _product()
        # The customer is the user model itself.
        customer = get_user_model().objects.create_user(
            username='r1', email='r1@x.test', password='x'
        )
        other = get_user_model().objects.create_user(username='r2', email='r2@x.test', password='x')
        Review.objects.create(
            product=product,
            customer=customer,
            rating=5,
            title='Bright',
            body='Lights the tent.',
            is_approved=True,
        )
        Review.objects.create(
            product=product,
            customer=other,
            rating=1,
            title='Spam',
            body='Buy now',
            is_approved=False,
        )
        md = render_product_markdown(product)
        self.assertIn('## Reviews', md)
        self.assertIn('Bright', md)
        self.assertNotIn('Spam', md)

    def test_availability_comes_from_the_stock_answer(self):
        from plugins.installed.seo.services.ai_feeds import render_product_markdown

        product = _product()
        with patch(
            'plugins.feed_mapping.availability_to_schema',
            return_value='https://schema.org/OutOfStock',
        ):
            md = render_product_markdown(product)
        self.assertIn('out of stock', md)
        self.assertNotIn('· in stock', md)


class LlmsTxtTests(TestCase):
    def _render(self):
        from plugins.installed.seo.services import render_llms_txt

        return render_llms_txt()

    def test_a_store_with_no_goods_lists_no_products_page_or_empty_heading(self):
        Category.objects.create(name='Tours', slug='tc-tours', is_active=True)
        out = self._render()
        self.assertNotIn('/products/)', out)
        self.assertNotIn('## Categories', out)
        self.assertNotIn('Morpheus store', out)

    def test_only_active_categories_with_goods_are_listed(self):
        lamps = Category.objects.create(name='Lamps', slug='tc-lamps', is_active=True)
        Category.objects.create(name='Hidden', slug='tc-hidden', is_active=False)
        Category.objects.create(name='Empty', slug='tc-empty', is_active=True)
        _product(category=lamps)
        out = self._render()
        self.assertIn('- [Lamps]', out)
        self.assertNotIn('Hidden', out)
        self.assertNotIn('- [Empty]', out)
        self.assertIn('/products/)', out)

    def test_the_title_is_the_stores_own_name(self):
        from core.models import StoreSettings

        StoreSettings.objects.create(store_name='Croatia Experience')
        self.assertTrue(self._render().startswith('# Croatia Experience'))


class IndexNowTests(TestCase):
    def _pinged(self, product):
        from plugins.registry import app_registry

        seo = app_registry.get('seo')
        with patch.object(seo, '_indexnow_push') as push:
            seo.on_product_updated(product)
        return push.called

    def test_an_active_product_is_pinged(self):
        self.assertTrue(self._pinged(_product()))

    def test_a_draft_and_a_service_are_not(self):
        self.assertFalse(self._pinged(_product(slug='tc-draft', sku='TC-2', status='draft')))
        self.assertFalse(self._pinged(_product(slug='tc-svc', sku='TC-3', product_type='service')))


class CoreWebVitalsUnitsTests(TestCase):
    def test_lcp_is_reported_in_seconds(self):
        from core.audit.models import AuditEvent
        from plugins.installed.seo.services import cwv_summary

        for value in (1200, 1800, 2400, 3000):
            AuditEvent.objects.create(
                event_type='cwv.report', metadata={'metric': 'LCP', 'value': value}
            )
        AuditEvent.objects.create(event_type='cwv.report', metadata={'metric': 'INP', 'value': 180})
        summary = cwv_summary()
        self.assertEqual(summary['lcp'], 2.4)  # the beacon's milliseconds, as Google's seconds
        self.assertEqual(summary['inp'], 180)
