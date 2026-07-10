"""Merchandising console tests (M3): surfaces index, take-control, preview."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.dynamics.models import SURFACE_CHOICES, DynamicBlock, DynamicGridItem


def _staff_client():
    user = get_user_model().objects.create_user(
        username='merch', email='m@example.com', password='x', is_staff=True
    )
    c = Client()
    c.force_login(user)
    return c


def _product(slug):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug,
        status='active',
        price=Money(Decimal('10'), 'USD'),
    )


class ConsoleIndexTests(TestCase):
    def test_anonymous_is_redirected(self):
        resp = Client().get('/dashboard/dynamics/')
        self.assertIn(resp.status_code, (302, 403))

    def test_index_lists_every_surface(self):
        from django.utils.html import escape

        resp = _staff_client().get('/dashboard/dynamics/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        for _key, label in SURFACE_CHOICES:
            self.assertIn(escape(label), body)
        self.assertIn('Take control', body)

    def test_controlled_surface_shows_block(self):
        DynamicBlock.objects.create(
            name='Hero takeover', surface='home_hero', strategy='smart', limit=4
        )
        body = _staff_client().get('/dashboard/dynamics/').content.decode()
        self.assertIn('Hero takeover', body)


class TakeControlTests(TestCase):
    def setUp(self):
        self.client = _staff_client()

    def test_creates_smart_block_and_redirects_to_editor(self):
        resp = self.client.post('/dashboard/dynamics/surface/home_featured/take/')
        block = DynamicBlock.objects.get(surface='home_featured')
        self.assertEqual(block.strategy, 'smart')
        self.assertEqual(block.limit, 8)
        self.assertTrue(block.enabled)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(str(block.pk), resp['Location'])

    def test_second_take_redirects_to_existing(self):
        self.client.post('/dashboard/dynamics/surface/home_hero/take/')
        self.client.post('/dashboard/dynamics/surface/home_hero/take/')
        self.assertEqual(DynamicBlock.objects.filter(surface='home_hero').count(), 1)

    def test_unknown_surface_rejected(self):
        self.client.post('/dashboard/dynamics/surface/not-a-surface/take/')
        self.assertEqual(DynamicBlock.objects.count(), 0)

    def test_get_does_not_create(self):
        self.client.get('/dashboard/dynamics/surface/home_hero/take/')
        self.assertEqual(DynamicBlock.objects.count(), 0)


class PreviewTests(TestCase):
    def setUp(self):
        self.client = _staff_client()

    def test_smart_preview_shows_score_breakdown(self):
        p = _product('starred')
        DynamicGridItem.objects.create(product=p, title=p.name, purchase_probability=0.8)
        block = DynamicBlock.objects.create(
            name='Featured', surface='home_featured', strategy='smart', limit=4
        )
        resp = self.client.get(f'/dashboard/dynamics/{block.pk}/preview/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('Starred', body)
        for label in ('probability', 'trend', 'session', 'recency'):
            self.assertIn(label, body)
        self.assertIn('Why is this here?', body)

    def test_autopilot_preview_offers_segment_selector(self):
        _product('any')
        block = DynamicBlock.objects.create(
            name='Auto', slot='home_below_grid', strategy='autopilot', limit=4
        )
        body = self.client.get(
            f'/dashboard/dynamics/{block.pk}/preview/?segment=mobile:morning:anon'
        ).content.decode()
        self.assertIn('Preview as segment', body)
        self.assertIn('mobile:morning:anon', body)

    def test_anonymous_preview_blocked(self):
        block = DynamicBlock.objects.create(name='B', slot='home_below_grid', strategy='smart')
        resp = Client().get(f'/dashboard/dynamics/{block.pk}/preview/')
        self.assertIn(resp.status_code, (302, 403))


class SurfaceSaveTests(TestCase):
    def test_save_accepts_surface_without_slot(self):
        client = _staff_client()
        resp = client.post(
            '/dashboard/dynamics/new/',
            {
                'name': 'PLP smart order',
                'slot': '',
                'surface': 'plp_default',
                'strategy': 'smart',
                'limit': '12',
                'sort_order': '50',
                'enabled': 'on',
                'layout': 'carousel',
                'columns': '4',
            },
        )
        self.assertEqual(resp.status_code, 302)
        block = DynamicBlock.objects.get(name='PLP smart order')
        self.assertEqual(block.surface, 'plp_default')
        self.assertEqual(block.slot, '')

    def test_save_rejects_neither_slot_nor_surface(self):
        client = _staff_client()
        client.post(
            '/dashboard/dynamics/new/',
            {'name': 'Nowhere', 'slot': '', 'surface': '', 'strategy': 'smart'},
        )
        self.assertEqual(DynamicBlock.objects.count(), 0)
