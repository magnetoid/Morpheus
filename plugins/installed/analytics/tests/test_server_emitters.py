# plugins/installed/analytics/tests/test_server_emitters.py
"""Server-side PRODUCT_VIEWED / SEARCH_PERFORMED events must carry the
visitor's session (funnels join on session_id) and the search query."""

from __future__ import annotations

from django.test import RequestFactory, TestCase

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.analytics.models import AnalyticsEvent


class _FakeProduct:
    slug = 'test-book'


class ServerEmitterTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _request(self):
        req = self.rf.get('/products/test-book/')
        req.user = type('Anon', (), {'is_authenticated': False})()
        req.COOKIES['morpheus_consent'] = '{"analytics": true, "functional": true, "marketing": true}'
        req.COOKIES['morph_aid'] = 'ck-emitter-test-0000000000000000'
        return req

    def test_product_viewed_hook_records_event_with_session(self):
        hook_registry.fire(
            MorpheusEvents.PRODUCT_VIEWED,
            product=_FakeProduct(),
            customer=None,
            request=self._request(),
        )
        evt = AnalyticsEvent.objects.get(name='product.viewed')
        self.assertEqual(evt.product_slug, 'test-book')
        self.assertIsNotNone(evt.session_id, 'server event must carry a session')

    def test_search_performed_hook_records_query(self):
        hook_registry.fire(
            MorpheusEvents.SEARCH_PERFORMED,
            query='dune',
            results_count=3,
            request=self._request(),
        )
        evt = AnalyticsEvent.objects.get(name='search.performed')
        self.assertEqual(evt.search_query, 'dune')
        self.assertIsNotNone(evt.session_id)
