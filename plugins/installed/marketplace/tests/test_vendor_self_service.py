"""Permission boundary + smoke tests for the vendor self-service flow.

The vendor edit endpoint is mutation-capable and gated on ownership —
exactly the kind of surface where a quiet permission leak would be
expensive. The boundary triplet (anon blocked / wrong-vendor blocked /
own-vendor allowed) locks in the security contract.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, Vendor


def _make_user(email: str, password: str = 'pw'):
    User = get_user_model()
    return User.objects.create_user(
        username=email,
        email=email,
        password=password,
    )


def _make_vendor(name: str, owner=None, **kwargs):
    slug = kwargs.pop('slug', name.lower().replace(' ', '-'))
    return Vendor.objects.create(name=name, slug=slug, owner=owner, **kwargs)


def _make_product(vendor, **kwargs):
    defaults = {
        'name': 'Sample Book',
        'sku': f'SKU-{vendor.slug}-{Product.objects.filter(vendor=vendor).count() + 1}',
        'status': 'active',
        'price': Money(Decimal('12.00'), 'USD'),
        'product_type': 'simple',
        'vendor': vendor,
    }
    defaults.update(kwargs)
    if 'slug' not in defaults:
        defaults['slug'] = (defaults['sku'] or 'book').lower()
    return Product.objects.create(**defaults)


class VendorProductsListPermissionTests(TestCase):
    """Triplet: anon → login redirect, customer-without-vendor →
    empty-state, approved vendor → 200 + own products only."""

    def setUp(self):
        self.client = Client()
        self.user_vendor = _make_user('owner@example.com')
        self.vendor = _make_vendor('Indie Press', owner=self.user_vendor)
        self.product = _make_product(
            self.vendor, name='Pinocchio', slug='pinocchio-test', sku='PIN-T-1'
        )

        # A different vendor + product to assert isolation
        self.user_other = _make_user('other@example.com')
        self.other_vendor = _make_vendor('Other Press', owner=self.user_other)
        self.other_product = _make_product(
            self.other_vendor, name='Other Book', slug='other-book-test', sku='OB-T-1'
        )

    def test_anon_redirects_to_login(self):
        resp = self.client.get('/vendor/me/products/')
        # @login_required → 302 to /auth/login/?next=...
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])

    def test_customer_without_vendor_sees_empty_state(self):
        user = _make_user('customer@example.com')
        self.client.force_login(user)
        resp = self.client.get('/vendor/me/products/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        # Per template: "not an approved vendor yet" branch
        self.assertIn('not an approved vendor', body.lower())
        # No product names leaked
        self.assertNotIn('Pinocchio', body)
        self.assertNotIn('Other Book', body)

    def test_vendor_sees_only_own_products(self):
        self.client.force_login(self.user_vendor)
        resp = self.client.get('/vendor/me/products/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('Pinocchio', body)
        # Critical: the OTHER vendor's product must not appear
        self.assertNotIn('Other Book', body)


class VendorProductEditPermissionTests(TestCase):
    """Triplet for the edit endpoint: anon → login, wrong vendor → 404
    (not 403, because we want URL-guess attacks to look like 'missing'
    rather than 'forbidden — try again'), own vendor → 200 + can save.
    """

    def setUp(self):
        self.client = Client()
        self.user_vendor = _make_user('edit-owner@example.com')
        self.vendor = _make_vendor('Edit Press', owner=self.user_vendor)
        self.product = _make_product(self.vendor, name='Edit Me', slug='edit-me-test', sku='EM-T-1')

        self.user_attacker = _make_user('attacker@example.com')
        self.attacker_vendor = _make_vendor('Attacker Press', owner=self.user_attacker)
        # Attacker's own product so they ARE an approved vendor (otherwise
        # they get the "not a vendor" 403 path, not the cross-vendor 404)
        _make_product(
            self.attacker_vendor, name='Attacker Book', slug='attacker-book-test', sku='AB-T-1'
        )

    def _url(self, product_id):
        return f'/vendor/me/products/{product_id}/'

    def test_anon_redirects(self):
        resp = self.client.get(self._url(self.product.id))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])

    def test_non_vendor_user_gets_403(self):
        user = _make_user('rando@example.com')
        self.client.force_login(user)
        resp = self.client.get(self._url(self.product.id))
        self.assertEqual(resp.status_code, 403)

    def test_other_vendor_cannot_edit(self):
        """The attacker IS an approved vendor (so they get past the 403),
        but Vendor B trying to edit Vendor A's product gets 404 —
        URL-guess attacks should look like the product doesn't exist."""
        self.client.force_login(self.user_attacker)
        resp = self.client.get(self._url(self.product.id))
        self.assertEqual(resp.status_code, 404)

    def test_other_vendor_cannot_post_either(self):
        """The double-check at fetch time means even a POST is blocked."""
        self.client.force_login(self.user_attacker)
        resp = self.client.post(
            self._url(self.product.id),
            {
                'name': 'HIJACKED',
                'status': 'archived',
                'price': '0.01',
                'short_description': '',
                'description': '',
            },
        )
        self.assertEqual(resp.status_code, 404)
        # Refresh from DB: nothing should have changed.
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Edit Me')
        self.assertEqual(self.product.status, 'active')

    def test_owner_can_view_form(self):
        self.client.force_login(self.user_vendor)
        resp = self.client.get(self._url(self.product.id))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('Edit Me', body)

    def test_owner_can_save_changes(self):
        self.client.force_login(self.user_vendor)
        resp = self.client.post(
            self._url(self.product.id),
            {
                'name': 'Edit Me — 2nd ed',
                'status': 'active',
                'price': '15.50',
                'short_description': 'A short pitch.',
                'description': 'A longer description with HTML.',
            },
        )
        self.assertEqual(resp.status_code, 302)  # redirect to /vendor/me/products/
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Edit Me — 2nd ed')
        self.assertEqual(self.product.short_description, 'A short pitch.')
        self.assertEqual(self.product.price.amount, Decimal('15.50'))

    def test_invalid_price_doesnt_save(self):
        self.client.force_login(self.user_vendor)
        original_price = self.product.price.amount
        resp = self.client.post(
            self._url(self.product.id),
            {
                'name': 'Still Edit Me',
                'status': 'active',
                'price': 'not-a-number',
                'short_description': '',
                'description': '',
            },
        )
        # Re-renders with an error (200, not 302/4xx)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode().lower()
        self.assertIn('price must be a non-negative number', body)
        # Price unchanged
        self.product.refresh_from_db()
        self.assertEqual(self.product.price.amount, original_price)
