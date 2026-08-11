"""Tests for live_commerce: model states, status hooks, storefront, permissions."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product
from plugins.installed.live_commerce import services
from plugins.installed.live_commerce.models import LiveEvent, LiveEventProduct
from plugins.installed.live_commerce.views import index as dashboard_index


def _event(**kw):
    now = timezone.now()
    defaults = {
        'title': 'Spring Show',
        'slug': 'spring-show',
        'scheduled_start': now + timedelta(days=1),
        'scheduled_end': now + timedelta(days=1, hours=1),
        'embed_url': 'https://www.youtube.com/embed/abc',
    }
    defaults.update(kw)
    return LiveEvent.objects.create(**defaults)


def _product(slug='book-1', name='Book One'):
    return Product.objects.create(name=name, slug=slug, sku=slug, price=Money(10, 'USD'))


class ModelStateTests(TestCase):
    def test_default_status_scheduled(self):
        self.assertEqual(_event().status, 'scheduled')

    def test_is_replay_requires_ended_and_recording(self):
        e = _event(status='ended', recording_url='https://youtu.be/x')
        self.assertTrue(e.is_replay)
        self.assertFalse(_event(slug='s2', status='ended').is_replay)
        self.assertFalse(
            _event(slug='s3', status='live', recording_url='https://youtu.be/x').is_replay
        )


class StatusTransitionTests(TestCase):
    def test_go_live_fires_started(self):
        e = _event()
        seen = []
        hook_registry.register(
            MorpheusEvents.LIVE_EVENT_STARTED, lambda **kw: seen.append(kw['live_event'])
        )
        changed = services.set_status(e, 'live')
        self.assertTrue(changed)
        self.assertEqual(e.status, 'live')
        self.assertEqual(seen, [e])

    def test_end_fires_ended(self):
        e = _event(status='live')
        seen = []
        hook_registry.register(
            MorpheusEvents.LIVE_EVENT_ENDED, lambda **kw: seen.append(kw['live_event'])
        )
        self.assertTrue(services.set_status(e, 'ended'))
        self.assertEqual(seen, [e])

    def test_noop_when_status_unchanged(self):
        e = _event(status='live')
        self.assertFalse(services.set_status(e, 'live'))

    def test_invalid_status_rejected(self):
        e = _event()
        self.assertFalse(services.set_status(e, 'bogus'))
        self.assertEqual(e.status, 'scheduled')


class StorefrontTests(TestCase):
    def test_event_page_lists_pinned_products_in_order(self):
        e = _event(status='live')
        p1, p2 = _product('book-1', 'One'), _product('book-2', 'Two')
        LiveEventProduct.objects.create(event=e, product=p2, sort_order=0)
        LiveEventProduct.objects.create(event=e, product=p1, sort_order=1)
        resp = Client().get(f'/live/{e.slug}/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        # Ordered by sort_order → p2 ('Two') appears before p1 ('One').
        self.assertLess(body.index('Two'), body.index('One'))
        # Product links carry the live UTM campaign.
        self.assertIn('utm_source=live', body)
        self.assertIn('utm_campaign=spring-show', body)

    def test_event_page_404_for_unknown_slug(self):
        self.assertEqual(Client().get('/live/nope/').status_code, 404)

    def test_index_lists_upcoming(self):
        _event()
        resp = Client().get('/live/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Spring Show', resp.content.decode())

    def test_teaser_hidden_with_no_events(self):
        # No events → featured_teaser() is None → teaser self-hides.
        self.assertIsNone(services.featured_teaser())

    def test_teaser_prefers_live_over_scheduled(self):
        _event(slug='sched')
        live = _event(slug='live-now', status='live')
        self.assertEqual(services.featured_teaser(), live)


class PermissionTests(TestCase):
    def test_dashboard_requires_staff(self):
        req = RequestFactory().get('/dashboard/live/')
        req.user = AnonymousUser()
        resp = dashboard_index(req)
        self.assertIn(resp.status_code, (302, 403))

    def test_dashboard_page_is_contributed(self):
        from plugins.registry import app_registry

        pages = [p for p in app_registry.dashboard_pages() if p.plugin == 'live_commerce']
        self.assertTrue(pages)


class DisableLitmusTests(TestCase):
    def test_storefront_block_is_contributed(self):
        from plugins.registry import app_registry

        blocks = [
            b
            for b in app_registry.storefront_blocks_for('home_below_grid')
            if b.plugin == 'live_commerce'
        ]
        self.assertTrue(blocks)
