"""Sticky buybox renders correctly: product_id present, variant select only for
multi-edition products, nothing when there are no variants."""

from __future__ import annotations

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

TEMPLATE = 'immersive_pdp/blocks/sticky_buybox.html'


def _product():
    return SimpleNamespace(id='prod-123', slug='a-book', name='A Book', price=None)


def _variant(vid, name):
    return SimpleNamespace(id=vid, name=name)


class StickyBuyboxRenderTests(SimpleTestCase):
    def test_single_variant_hides_select(self):
        html = render_to_string(
            TEMPLATE, {'product': _product(), 'variants': [_variant('v1', 'Paperback')]}
        )
        self.assertIn('name="product_id" value="prod-123"', html)
        self.assertIn('name="variant_id" value="v1"', html)  # hidden input
        self.assertNotIn('<select', html)
        self.assertIn('Add to bag', html)

    def test_multiple_variants_show_select(self):
        html = render_to_string(
            TEMPLATE,
            {
                'product': _product(),
                'variants': [_variant('v1', 'Paperback'), _variant('v2', 'Hardcover')],
            },
        )
        self.assertIn('<select name="variant_id"', html)
        self.assertIn('Hardcover', html)
        self.assertIn('Edition', html)  # not a bare "Variant" label

    def test_no_variants_renders_nothing(self):
        html = render_to_string(TEMPLATE, {'product': _product(), 'variants': []})
        self.assertNotIn('immersive-buybox', html.strip())
