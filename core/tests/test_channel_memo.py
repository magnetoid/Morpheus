"""current_channel() must resolve at most once per request (memoized)."""

from django.test import RequestFactory, TestCase

from core.channels import current_channel
from core.models import StoreChannel


class ChannelMemoTests(TestCase):
    def setUp(self):
        StoreChannel.objects.create(
            slug='default', name='Default', domain='testserver', is_default=True
        )

    def test_second_call_hits_no_db(self):
        request = RequestFactory().get('/dashboard/')
        first = current_channel(request)  # warms the per-request memo
        self.assertIsNotNone(first)
        with self.assertNumQueries(0):
            second = current_channel(request)
        self.assertIs(second, first)

    def test_distinct_requests_resolve_independently(self):
        r1 = RequestFactory().get('/')
        r2 = RequestFactory().get('/')
        current_channel(r1)
        # A fresh request has its own memo slot, so it resolves again.
        with self.assertNumQueries(1):
            current_channel(r2)
