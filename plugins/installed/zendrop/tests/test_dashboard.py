"""The Zendrop page and its actions."""

from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from plugins.installed.zendrop.tests._fixtures import (
    paid_order,
    physical_product,
    refetch,
    staff_user,
)

PAGE = '/dashboard/apps/zendrop/orders/'


class DashboardTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.force_login(staff_user())
        self.product, self.variant = physical_product()
        self.order = paid_order([(self.product, self.variant, 1)])

    def test_page_shows_the_sheet_and_the_missing_token_hint(self):
        response = self.client.get(PAGE)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(self.order.order_number, body)
        self.assertIn('Mara Jovanović', body)
        self.assertIn('not mapped', body)
        self.assertIn('No access token saved', body)

    def test_mark_placed_then_ship_from_the_page(self):
        response = self.client.post(
            f'/dashboard/zendrop/orders/{self.order.order_number}/placed/',
            {'zendrop_order_number': 'ZD-5'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(refetch(self.order).status, 'processing')
        body = self.client.get(PAGE).content.decode()
        self.assertIn('ZD-5', body)

        response = self.client.post(
            f'/dashboard/zendrop/orders/{self.order.order_number}/ship/',
            {'tracking_number': 'ZD77', 'carrier': 'USPS'},
        )
        self.assertEqual(response.status_code, 302)
        order = refetch(self.order)
        self.assertEqual((order.status, order.tracking_number), ('shipped', 'ZD77'))

    def test_tracking_upload_ships_and_reports(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.post(f'/dashboard/zendrop/orders/{self.order.order_number}/placed/', {})
        upload = SimpleUploadedFile(
            'tracking.csv',
            f'Order number,Tracking number\n{self.order.order_number},ZD9\n'.encode(),
            content_type='text/csv',
        )
        response = self.client.post('/dashboard/zendrop/import/tracking/', {'csv': upload})
        self.assertEqual(response.status_code, 200)
        self.assertIn('ZD9', response.content.decode())
        self.assertEqual(refetch(self.order).status, 'shipped')

    def test_connection_test_reports_through_messages(self):
        from plugins.installed.zendrop.services import mcp
        from plugins.registry import app_registry

        plugin = app_registry.get('zendrop')
        plugin.set_config('access_token', 'tok-123')
        self.addCleanup(plugin.invalidate_config_cache)
        with mock.patch.object(
            mcp,
            'list_tools',
            return_value={
                'server': {'name': 'Zendrop MCP', 'version': '1'},
                'protocol': 'x',
                'tools': [{'name': 'list_orders', 'description': 'orders'}],
            },
        ):
            response = self.client.post('/dashboard/zendrop/connection/test/', follow=True)
        body = response.content.decode()
        self.assertIn('Connected', body)
        self.assertIn('list_orders', body)

    def test_non_staff_cannot_act(self):
        self.client.logout()
        response = self.client.post(
            f'/dashboard/zendrop/orders/{self.order.order_number}/placed/', {}
        )
        self.assertIn(response.status_code, (302, 403))
        self.assertEqual(refetch(self.order).status, 'confirmed')
