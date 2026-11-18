"""The EU legal guarantee notice on a goods page (v0.178.0).

Commission Implementing Regulation (EU) 2025/1960 fixes the notice a trader selling
goods to consumers shows from 27 September 2026, and none of its elements may be
edited, so the app shows the Official Journal's own artwork whole, in colour and
never folded away, with the same text for a screen reader. It is a setting, off by
default: on, every product sold as goods shows it under the description; a service
or a download never does, and neither does a store that switches the app off.
"""

from __future__ import annotations

from pathlib import Path

from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import TestCase
from PIL import Image

from plugins import config_schema
from plugins.installed.product_safety.safety import (
    GUARANTEE_NOTICE,
    GUARANTEE_NOTICE_FILES,
    shows_guarantee_notice,
)
from plugins.installed.product_safety.tests.test_product_safety import (
    _call,
    _product,
    _StoreDetails,
)
from plugins.registry import app_registry

STATIC = Path(__file__).resolve().parent.parent / 'static'


def _block(product) -> str:
    return render_to_string(
        'product_safety/blocks/legal_guarantee.html', {'product': {'id': str(product.pk)}}
    )


class NoticeTests(_StoreDetails, TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_off_by_default(self):
        goods = _product()
        self.assertFalse(shows_guarantee_notice(goods))
        self.assertNotIn('data-legal-guarantee', _block(goods))

    def test_switched_on_a_goods_page_shows_the_whole_notice_and_its_text(self):
        self.set_store(**{GUARANTEE_NOTICE: True})
        html = _block(_product())
        self.assertIn('data-legal-guarantee', html)
        self.assertIn('lang="en"', html)
        self.assertIn('/static/product_safety/legal-guarantee-notice-en-500.jpg', html)
        self.assertIn('legal-guarantee-notice-en-1000.jpg 1000w', html)
        self.assertIn('width="500" height="706"', html)
        # The artwork is never inside a fold; only its text alternative is.
        self.assertLess(html.index('<img'), html.index('<details'))
        for line in (
            'Minimum two-year legal guarantee protection for goods sold in the European Union.',
            'free repair or free replacement',
            'For second-hand goods, a shorter period may apply, but not less than one year.',
            'href="https://europa.eu/youreurope/guarantees"',
            'Provide proof of purchase, such as a receipt, invoice, or bank statement.',
            'commercial guarantee of durability',
        ):
            self.assertIn(line, html)

    def test_a_service_or_a_download_never_shows_it(self):
        self.set_store(**{GUARANTEE_NOTICE: True})
        for product in (
            _product(slug='tour', sku='T-1', product_type='service'),
            _product(slug='ebook', sku='E-1', product_type='digital', requires_shipping=False),
            _product(slug='pdf', sku='P-1', requires_shipping=False),
        ):
            with self.subTest(product=product.slug):
                self.assertNotIn('data-legal-guarantee', _block(product))

    def test_a_switch_stored_as_text_still_reads(self):
        self.set_store(**{GUARANTEE_NOTICE: 'true'})
        self.assertTrue(shows_guarantee_notice(_product()))
        self.set_store(**{GUARANTEE_NOTICE: 'false'})
        self.assertFalse(shows_guarantee_notice(_product(slug='b', sku='B-1')))

    def test_the_product_page_carries_it_under_the_description(self):
        self.set_store(**{GUARANTEE_NOTICE: True})
        p = _product()
        body = self.client.get(f'/products/{p.slug}/').content.decode()
        self.assertIn('data-legal-guarantee', body)

    def test_the_files_are_the_official_artwork_at_the_sizes_the_page_names(self):
        for name, width, height in zip(
            GUARANTEE_NOTICE_FILES['en'], (500, 1000), (706, 1412), strict=True
        ):
            with self.subTest(file=name), Image.open(STATIC / name) as image:
                self.assertEqual(image.size, (width, height))
                self.assertEqual(image.mode, 'RGB')  # in colour, as the regulation asks

    def test_linda_reads_whether_the_page_shows_it_and_may_switch_it(self):
        self.set_store(**{GUARANTEE_NOTICE: True})
        p = _product()
        result = _call('products.safety_info', {'slug': p.slug})
        self.assertIs(result.output['shown']['legal_guarantee_notice'], True)
        self.assertIn('the EU legal guarantee notice', result.display)
        prop = config_schema.properties(app_registry.get('product_safety'))[GUARANTEE_NOTICE]
        self.assertEqual(prop['default'], False)
        self.assertTrue(config_schema.agent_writable(GUARANTEE_NOTICE, prop))


class DisabledNoticeTests(_StoreDetails, TestCase):
    def setUp(self):
        cache.clear()
        self.set_store(**{GUARANTEE_NOTICE: True})
        app_registry.deactivate('product_safety')
        self.addCleanup(cache.clear)
        self.addCleanup(app_registry.activate, 'product_safety')

    def test_a_store_without_the_app_shows_no_notice(self):
        p = _product()
        body = self.client.get(f'/products/{p.slug}/').content.decode()
        self.assertNotIn('data-legal-guarantee', body)
