"""Every product type sees the editor's Basics, and every priced type its Pricing.

The editor hides a card whose ``data-pt-show`` list does not name the product's
type. Basics and Pricing listed the four original types, so when booking listings
became ``service`` products (v0.109.0) the editor showed an experience's booking
card and status but not its name, descriptions, category, host or price.
"""

from __future__ import annotations

from decimal import Decimal
from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

_VOID = {
    'area',
    'base',
    'br',
    'col',
    'embed',
    'hr',
    'img',
    'input',
    'link',
    'meta',
    'source',
    'track',
    'wbr',
}
BASICS = ('name', 'slug', 'sku', 'short_description', 'description', 'category', 'vendor')
PRICING = ('price', 'compare_at_price')


class _Gates(HTMLParser):
    """For each named control, the ``data-pt-show`` lists of the elements around it."""

    def __init__(self, form_id: str = 'product-form'):
        super().__init__(convert_charrefs=True)
        self.form_id = form_id
        self._stack: list[tuple[str, frozenset | None, bool]] = []
        self.controls: dict[str, list[list[frozenset]]] = {}

    def _in_form(self) -> bool:
        return any(is_form for _, _, is_form in self._stack)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        named = tag in ('input', 'select', 'textarea') and attrs.get('name')
        # Only the product form's own controls: the variant forms reuse `name`, `description`…
        if named and self._in_form():
            gates = [gate for _, gate, _ in self._stack if gate is not None]
            self.controls.setdefault(attrs['name'], []).append(gates)
        if tag in _VOID:
            return
        raw = attrs.get('data-pt-show')
        gate = frozenset(s.strip() for s in raw.split(',')) if raw is not None else None
        self._stack.append((tag, gate, tag == 'form' and attrs.get('id') == self.form_id))

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                return

    def visible(self, name: str, product_type: str) -> bool:
        """Whether some copy of the control sits in no card hidden for this type."""
        return any(
            all(product_type in gate for gate in gates) for gates in self.controls.get(name, [])
        )


class ProductTypeCardsTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='typecards', email='typecards@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        from plugins.installed.catalog.models import Vendor

        Vendor.objects.create(
            name='Type Cards Host', slug='type-cards-host'
        )  # the host select needs one

    def _editor(self, product_type: str) -> _Gates:
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name=f'{product_type} thing',
            slug=f'{product_type}-thing',
            sku=f'TC-{product_type}',
            product_type=product_type,
            price=Money(Decimal('10.00'), 'EUR'),
        )
        url = reverse('admin_dashboard:product_edit', kwargs={'product_id': product.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        parser = _Gates()
        parser.feed(resp.content.decode())
        return parser

    def test_every_type_shows_the_basics(self):
        from plugins.installed.catalog.models import Product

        for product_type, _ in Product.PRODUCT_TYPES:
            with self.subTest(product_type=product_type):
                editor = self._editor(product_type)
                hidden = [name for name in BASICS if not editor.visible(name, product_type)]
                self.assertEqual(hidden, [], f'{product_type} hides {hidden}')

    def test_a_service_shows_its_price(self):
        editor = self._editor('service')
        hidden = [name for name in PRICING if not editor.visible(name, 'service')]
        self.assertEqual(hidden, [])
