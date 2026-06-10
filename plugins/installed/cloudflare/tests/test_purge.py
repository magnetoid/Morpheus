"""Cloudflare purge service tests using a fake API client."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.cloudflare.models import (
    CacheInvalidation,
    CloudflareAccount,
    CloudflareZone,
)
from plugins.installed.cloudflare.services import (
    CloudflareClient,
    CloudflareError,
    purge_everything,
    purge_urls,
)


class _FakeSession:
    def __init__(self, *, raise_on=None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._raise_on = raise_on

    def request(self, method: str, path: str, *, payload: dict = None, params: dict = None) -> dict:
        # Mirrors CloudflareClient._request → session.request(method, path, ...).
        self.calls.append((path, payload))
        if self._raise_on and self._raise_on in path:
            raise CloudflareError('boom')
        return {'success': True, 'result': {'id': 'inv-123'}}


class CloudflarePurgeTests(TestCase):
    def setUp(self) -> None:
        self.account = CloudflareAccount.objects.create(label='t', api_token='tok')
        self.zone = CloudflareZone.objects.create(
            account=self.account,
            zone_id='zone-1',
            domain='shop.example',
        )

    def test_purge_urls_records_succeeded_invalidation(self):
        session = _FakeSession()
        client = CloudflareClient(api_token='tok', session=session)
        inv = purge_urls(
            zone=self.zone,
            urls=['https://shop.example/p/x'],
            triggered_by='test',
            client=client,
        )
        self.assertEqual(inv.status, 'succeeded')
        self.assertEqual(inv.scope, 'urls')
        self.assertEqual(len(session.calls), 1)
        self.assertIn('purge_cache', session.calls[0][0])

    def test_purge_everything_records_purge_everything_scope(self):
        session = _FakeSession()
        client = CloudflareClient(api_token='tok', session=session)
        inv = purge_everything(zone=self.zone, client=client)
        self.assertEqual(inv.scope, 'purge_everything')
        self.assertEqual(inv.status, 'succeeded')
        self.assertEqual(session.calls[0][1], {'purge_everything': True})

    def test_failed_purge_records_error(self):
        session = _FakeSession(raise_on='purge_cache')
        client = CloudflareClient(api_token='tok', session=session)
        inv = purge_urls(zone=self.zone, urls=['https://x'], client=client)
        self.assertEqual(inv.status, 'failed')
        self.assertIn('boom', inv.error_message)

    def test_zone_last_purge_at_updates_on_success(self):
        session = _FakeSession()
        client = CloudflareClient(api_token='tok', session=session)
        purge_urls(zone=self.zone, urls=['https://shop.example/'], client=client)
        self.zone.refresh_from_db()
        self.assertIsNotNone(self.zone.last_purge_at)


class CloudflareClientErrorTests(TestCase):
    def test_purge_requires_at_least_one_target(self):
        client = CloudflareClient(api_token='tok', session=_FakeSession())
        with self.assertRaises(ValueError):
            client.purge_cache('zone-1')


class CloudflareInvalidationCounterTests(TestCase):
    def test_invalidation_count_increments(self):
        account = CloudflareAccount.objects.create(label='c', api_token='tok')
        zone = CloudflareZone.objects.create(account=account, zone_id='z', domain='a.example')
        client = CloudflareClient(api_token='tok', session=_FakeSession())
        purge_urls(zone=zone, urls=['https://a.example/p/1'], client=client)
        purge_urls(zone=zone, urls=['https://a.example/p/2'], client=client)
        self.assertEqual(CacheInvalidation.objects.filter(zone=zone).count(), 2)
