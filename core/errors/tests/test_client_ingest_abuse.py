"""The anonymous browser-error endpoint cannot be used to fill the error log.

Its per-address limit hashed the FIRST X-Forwarded-For entry, which the client
writes itself (the CDN appends the real address after it), so a new forged value
per request was a new bucket. A body that is not UTF-8 raised past the JSON check
and answered 500, which was then recorded too.
"""

from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase

from core.errors import views
from core.errors.models import ErrorEvent


def _post(ip: str, forged: str):
    return RequestFactory().post(
        '/api/errors/client/', HTTP_CF_CONNECTING_IP=ip, HTTP_X_FORWARDED_FOR=f'{forged}, {ip}'
    )


class ClientIngestAbuseTests(TestCase):
    def setUp(self):
        cache.delete(views._ANON_ROWS_KEY)
        self.addCleanup(cache.delete, views._ANON_ROWS_KEY)

    def _forget(self, ip: str) -> None:
        key = views._bucket_key(_post(ip, ip))
        cache.delete(key)
        self.addCleanup(cache.delete, key)

    def test_a_forged_forwarded_address_is_still_one_bucket(self):
        self._forget('198.51.100.7')
        limited = [
            views._rate_limited(_post('198.51.100.7', f'10.0.{i // 250}.{i % 250}'))
            for i in range(views._RL_MAX + 1)
        ]
        self.assertFalse(any(limited[: views._RL_MAX]))
        self.assertTrue(limited[-1])

    def test_anonymous_reports_have_a_store_wide_cap(self):
        ips = [f'203.0.113.{i}' for i in range(4)]
        for ip in ips:
            self._forget(ip)
        with mock.patch.object(views, '_ANON_ROWS_PER_MINUTE', 3):
            limited = [views._rate_limited(_post(ip, ip)) for ip in ips]
        self.assertEqual(limited, [False, False, False, True])

    def test_a_signed_in_report_is_not_held_by_the_store_wide_cap(self):
        ips = ['203.0.113.50', '203.0.113.51']
        for ip in ips:
            self._forget(ip)
        with mock.patch.object(views, '_ANON_ROWS_PER_MINUTE', 1):
            views._rate_limited(_post(ips[0], ips[0]))
            request = _post(ips[1], ips[1])
            request.user = mock.Mock(is_authenticated=True)
            self.assertFalse(views._rate_limited(request))

    def test_a_body_that_is_not_utf8_is_a_400_and_nothing_is_stored(self):
        response = Client().post(
            '/api/errors/client/', data=b'\xff\xfe\x00junk', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ErrorEvent.objects.exists())
