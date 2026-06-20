"""core.ratelimit — client identity (CF-Connecting-IP), staff exemption, budget."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from core.ratelimit import RateLimitMiddleware, _client_id

User = get_user_model()


def _ok(_request):
    return HttpResponse('ok')


class ClientIdTests(TestCase):
    def test_cf_connecting_ip_wins_over_xff(self):
        # Behind Cloudflare the real client is CF-Connecting-IP; XFF can collapse
        # to a shared proxy IP through the chain (the bug that funneled everyone
        # into one bucket).
        r = RequestFactory().get(
            '/', HTTP_CF_CONNECTING_IP='9.9.9.9', HTTP_X_FORWARDED_FOR='10.0.0.1, 172.16.0.1'
        )
        self.assertEqual(_client_id(r), '9.9.9.9')

    def test_falls_back_to_xff_then_remote(self):
        r = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='8.8.8.8, 172.16.0.1')
        self.assertEqual(_client_id(r), '8.8.8.8')


@override_settings(MORPHEUS_RATELIMIT_ENABLED=True, MORPHEUS_RATELIMIT_PER_MINUTE=3)
class RateLimitMiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()
        self.rf = RequestFactory()
        self.mw = RateLimitMiddleware(_ok)

    def _req(self, *, cf='1.2.3.4', path='/shop/', user=None):
        r = self.rf.get(path, HTTP_CF_CONNECTING_IP=cf)
        r.user = user or AnonymousUser()
        return r

    def test_anonymous_limited_after_budget(self):
        for _ in range(3):
            self.assertEqual(self.mw(self._req()).status_code, 200)
        self.assertEqual(self.mw(self._req()).status_code, 429)  # 4th exceeds limit=3

    def test_distinct_client_ips_have_separate_buckets(self):
        for _ in range(3):
            self.mw(self._req(cf='1.1.1.1'))
        # A different real client IP is unaffected — proves per-client bucketing.
        self.assertEqual(self.mw(self._req(cf='2.2.2.2')).status_code, 200)

    def test_staff_is_never_limited(self):
        staff = User.objects.create_user(
            username='s', email='s@x.test', password='x', is_staff=True
        )
        for _ in range(10):  # well over limit=3
            self.assertEqual(self.mw(self._req(user=staff)).status_code, 200)

    def test_bypassed_path_skips(self):
        for _ in range(10):
            self.assertEqual(self.mw(self._req(path='/static/app.css')).status_code, 200)
