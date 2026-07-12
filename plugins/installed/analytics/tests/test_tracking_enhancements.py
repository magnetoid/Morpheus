import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase

from plugins.installed.analytics.models import AnalyticsEvent
from plugins.installed.analytics.services import get_or_create_session
from plugins.installed.analytics.views import track_beacon

User = get_user_model()


class AnalyticsTrackingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        # The beacon's per-IP rate-limit counter lives in the shared locmem
        # cache and survives across TestCases in the same process.
        cache.clear()

    def test_get_or_create_session_cross_device_id(self):
        """Verify cross_device_id and geo tracking works"""
        request = self.factory.get('/')
        request.META['HTTP_CF_IPCOUNTRY'] = 'US'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0'
        request.COOKIES['morpheus_consent'] = '{"analytics": true, "functional": true, "marketing": true}'
        request.user = self.user

        session = get_or_create_session(request)
        self.assertIsNotNone(session.cross_device_id)
        self.assertTrue(session.is_consented)
        self.assertEqual(session.geo_location.get('country'), 'US')
        self.assertEqual(session.device_specs.get('browser'), 'Mozilla/5.0')

    def test_track_beacon_new_metrics(self):
        """Verify the beacon correctly processes new scroll, duration, and error metrics"""
        payload = {
            'name': 'scroll.depth',
            'kind': 'scroll',
            'scroll_depth': 75,
            'duration_ms': 12000,
            'is_realtime': True,
        }
        request = self.factory.post(
            '/track/beacon/', data=json.dumps(payload), content_type='application/json'
        )
        # Mock session behavior for test
        request.COOKIES['morph_aid'] = 'test-cookie-123'

        response = track_beacon(request)
        self.assertEqual(response.status_code, 204)

        event = AnalyticsEvent.objects.last()
        self.assertEqual(event.kind, 'scroll')
        self.assertEqual(event.scroll_depth, 75)
        self.assertEqual(event.duration_ms, 12000)
        self.assertTrue(event.is_realtime)

    def test_error_tracking(self):
        """Verify error context is captured"""
        payload = {
            'name': 'api.error',
            'kind': 'error',
            'error_context': {'code': 500, 'message': 'Internal Server Error'},
        }
        request = self.factory.post(
            '/track/beacon/', data=json.dumps(payload), content_type='application/json'
        )
        response = track_beacon(request)
        self.assertEqual(response.status_code, 204)

        event = AnalyticsEvent.objects.last()
        self.assertEqual(event.kind, 'error')
        self.assertEqual(event.error_context.get('code'), 500)
