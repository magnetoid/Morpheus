"""The three data-ajax CREATE forms must speak JSON both ways (UX audit P0#1).

Before the 2026-07 UX batch, ``product_new`` / ``customer_new`` /
``coupon_new`` answered AJAX submits with a redirect or an HTML re-render:
dashboard.js reads any 200 non-JSON as success, so invalid input silently
dropped the record while the merchant saw "Saved" — and a valid create left
the merchant on the still-filled New form where a second submit duplicates
the record. Contract under test:

  * invalid AJAX POST → 400 ``{ok: false, errors: {...}}``
  * valid AJAX POST   → 200 ``{ok: true, redirect: <edit url>}``
  * non-AJAX POSTs keep the classic redirect / re-render behaviour
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

_AJAX = {'X-Requested-With': 'XMLHttpRequest'}


class _StaffClientMixin(TestCase):
    def setUp(self):
        self.client = Client()
        staff = get_user_model().objects.create_user(
            username='ajaxstaff', email='ajaxstaff@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)


class ProductCreateAjaxTests(_StaffClientMixin):
    def test_invalid_ajax_post_returns_json_errors(self):
        resp = self.client.post(reverse('admin_dashboard:product_new'), {}, headers=_AJAX)
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['ok'])
        self.assertIn('name', data['errors'])

    def test_valid_ajax_post_creates_and_returns_edit_redirect(self):
        from plugins.installed.catalog.models import Product

        resp = self.client.post(
            reverse('admin_dashboard:product_new'),
            {'name': 'Ajax Book', 'status': 'draft', 'product_type': 'simple', 'price': '9.99'},
            headers=_AJAX,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        product = Product.objects.get(name='Ajax Book')
        self.assertEqual(
            data['redirect'],
            reverse('admin_dashboard:product_edit', kwargs={'product_id': product.id}),
        )

    def test_non_ajax_invalid_post_rerenders_form(self):
        resp = self.client.post(reverse('admin_dashboard:product_new'), {})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'admin_dashboard/product_form.html')


class CustomerCreateAjaxTests(_StaffClientMixin):
    def test_invalid_ajax_post_returns_json_errors(self):
        resp = self.client.post(reverse('admin_dashboard:customer_new'), {}, headers=_AJAX)
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['ok'])
        self.assertIn('email', data['errors'])

    def test_valid_ajax_post_creates_and_returns_edit_redirect(self):
        resp = self.client.post(
            reverse('admin_dashboard:customer_new'),
            {'email': 'ajax-created@x.test', 'source': 'manual'},
            headers=_AJAX,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        customer = get_user_model().objects.get(email='ajax-created@x.test')
        self.assertEqual(
            data['redirect'],
            reverse('admin_dashboard:customer_edit', kwargs={'customer_id': customer.id}),
        )


class CouponCreateAjaxTests(_StaffClientMixin):
    def test_invalid_ajax_post_returns_json_errors(self):
        resp = self.client.post(reverse('admin_dashboard:coupon_new'), {}, headers=_AJAX)
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['ok'])
        self.assertIn('code', data['errors'])

    def test_valid_ajax_post_creates_and_returns_edit_redirect(self):
        from plugins.installed.marketing.models import Coupon

        resp = self.client.post(
            reverse('admin_dashboard:coupon_new'),
            {
                'code': 'AJAX10',
                'name': 'Ajax test coupon',
                'discount_type': 'percentage',
                'discount_value': '10',
            },
            headers=_AJAX,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        coupon = Coupon.objects.get(code='AJAX10')
        self.assertEqual(
            data['redirect'],
            reverse('admin_dashboard:coupon_edit', kwargs={'coupon_id': coupon.id}),
        )
