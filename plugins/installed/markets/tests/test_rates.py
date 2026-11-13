"""Exchange rates: the ECB fetch, manual rates, the task and the health check."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import ExchangeRate
from plugins.installed.markets import rates, tasks
from plugins.installed.markets.models import Market

ECB_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
    xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <gesmes:subject>Reference rates</gesmes:subject>
  <Cube><Cube time="2026-11-12">
    <Cube currency="USD" rate="1.25"/>
    <Cube currency="JPY" rate="150"/>
    <Cube currency="RSD" rate="117.2"/>
  </Cube></Cube>
</gesmes:Envelope>"""


def _fake_response(body=ECB_XML):
    return mock.Mock(content=body, raise_for_status=mock.Mock())


def _patch_ecb(body=ECB_XML):
    return mock.patch('core.net.outbound_request', return_value=_fake_response(body))


def _market(currency, **extra):
    return Market.objects.create(code=currency.lower(), label=currency, currency=currency, **extra)


def _row(base, quote):
    return ExchangeRate.objects.get(base_currency=base, quote_currency=quote)


@override_settings(STORE_CURRENCY='USD')
class FetchEcbTests(TestCase):
    def test_usd_store(self):
        with _patch_ecb() as call:
            out = rates.fetch_ecb()
        self.assertEqual(call.call_args.args[:2], ('GET', rates.ECB_URL))
        self.assertEqual(out['date'], '2026-11-12')
        self.assertEqual(out['written'], 3)
        self.assertEqual(_row('USD', 'EUR').rate, Decimal('0.8'))
        self.assertEqual(_row('USD', 'JPY').rate, Decimal('120'))
        self.assertEqual(_row('USD', 'EUR').source, 'ecb')
        self.assertFalse(ExchangeRate.objects.filter(quote_currency='USD').exists())

    @override_settings(STORE_CURRENCY='EUR')
    def test_eur_store(self):
        with _patch_ecb():
            rates.fetch_ecb()
        self.assertEqual(_row('EUR', 'USD').rate, Decimal('1.25'))
        self.assertEqual(_row('EUR', 'RSD').rate, Decimal('117.2'))
        self.assertFalse(ExchangeRate.objects.filter(quote_currency='EUR').exists())

    def test_manual_rate_is_kept(self):
        rates.set_manual_rate('EUR', Decimal('0.5'))
        with _patch_ecb():
            out = rates.fetch_ecb()
        self.assertEqual(out['kept_manual'], ['EUR'])
        self.assertEqual(_row('USD', 'EUR').rate, Decimal('0.5'))
        self.assertEqual(_row('USD', 'EUR').source, 'manual')
        self.assertEqual(_row('USD', 'JPY').source, 'ecb')

    def test_clearing_a_manual_rate_lets_the_next_fetch_fill_it(self):
        rates.set_manual_rate('EUR', Decimal('0.5'))
        rates.set_manual_rate('EUR', None)
        self.assertFalse(ExchangeRate.objects.exists())
        with _patch_ecb():
            rates.fetch_ecb()
        self.assertEqual(_row('USD', 'EUR').source, 'ecb')

    def test_clearing_never_deletes_an_ecb_row(self):
        with _patch_ecb():
            rates.fetch_ecb()
        rates.set_manual_rate('EUR', None)
        self.assertTrue(ExchangeRate.objects.filter(quote_currency='EUR').exists())

    def test_bad_manual_rates(self):
        for bad in (Decimal(0), Decimal(-1), Decimal('NaN')):
            with self.assertRaises(ValidationError):
                rates.set_manual_rate('EUR', bad)
        with self.assertRaises(ValidationError):
            rates.set_manual_rate('USD', Decimal(1))

    def test_failures_raise(self):
        with _patch_ecb(b'not xml'), self.assertRaises(ET.ParseError):
            rates.fetch_ecb()
        with _patch_ecb(b'<a/>'), self.assertRaises(ValueError):
            rates.fetch_ecb()
        with (
            mock.patch('core.net.outbound_request', side_effect=OSError('down')),
            self.assertRaises(OSError),
        ):
            rates.fetch_ecb()

    @override_settings(STORE_CURRENCY='CHF')
    def test_a_store_currency_the_ecb_lacks_raises(self):
        with _patch_ecb(), self.assertRaises(ValueError):
            rates.fetch_ecb()


@override_settings(STORE_CURRENCY='USD')
class RateRowTests(TestCase):
    def test_rows_for_active_foreign_markets_only(self):
        _market('USD')
        _market('EUR')
        _market('JPY', is_active=False)
        rows = rates.rate_rows()
        self.assertEqual([r['currency'] for r in rows], ['EUR'])
        self.assertTrue(rows[0]['stale'])
        self.assertIsNone(rows[0]['rate'])

    def test_current_stale_and_manual(self):
        _market('EUR')
        _market('RSD')
        with _patch_ecb():
            rates.fetch_ecb()
        ExchangeRate.objects.filter(quote_currency='EUR').update(
            fetched_at=timezone.now() - timedelta(days=4)
        )
        by = {r['currency']: r for r in rates.rate_rows()}
        self.assertTrue(by['EUR']['stale'])
        self.assertFalse(by['RSD']['stale'])
        rates.set_manual_rate('EUR', Decimal('0.9'))
        ExchangeRate.objects.filter(quote_currency='EUR').update(
            fetched_at=timezone.now() - timedelta(days=40)
        )
        by = {r['currency']: r for r in rates.rate_rows()}
        self.assertFalse(by['EUR']['stale'])
        self.assertEqual(by['EUR']['source'], 'manual')


@override_settings(STORE_CURRENCY='USD')
class TaskTests(TestCase):
    def test_skips_without_a_foreign_market(self):
        _market('USD')
        with _patch_ecb() as call:
            self.assertIsNone(tasks.fetch_exchange_rates())
        call.assert_not_called()

    def test_skips_when_rates_are_manual(self):
        _market('EUR')
        with (
            mock.patch.object(tasks, 'rate_source', return_value='manual'),
            _patch_ecb() as call,
        ):
            self.assertIsNone(tasks.fetch_exchange_rates())
        call.assert_not_called()

    def test_fetches_for_a_foreign_market(self):
        _market('EUR')
        with _patch_ecb():
            self.assertEqual(tasks.fetch_exchange_rates()['written'], 3)

    def test_a_failed_fetch_is_logged_not_raised(self):
        _market('EUR')
        with (
            mock.patch('core.net.outbound_request', side_effect=OSError('down')),
            self.assertLogs('morpheus.markets', 'WARNING'),
        ):
            self.assertIsNone(tasks.fetch_exchange_rates())

    def test_rate_source_defaults_to_ecb(self):
        self.assertEqual(tasks.rate_source(), 'ecb')


@override_settings(STORE_CURRENCY='USD')
class HealthAndBeatTests(TestCase):
    def check(self):
        from morpheus.core import MorpheusEvents, hook_registry

        out = hook_registry.filter(MorpheusEvents.HEALTH_CHECKS, value=[])
        return next(c for c in out if c['name'] == 'Exchange rates are current')

    def test_passes_when_no_market_needs_a_rate(self):
        _market('USD')
        self.assertTrue(self.check()['ok'])

    def test_fails_naming_the_currency(self):
        _market('EUR')
        result = self.check()
        self.assertFalse(result['ok'])
        self.assertIn('EUR (no rate)', result['detail'])

    def test_passes_with_a_current_rate(self):
        _market('EUR')
        rates.set_manual_rate('EUR', Decimal('0.9'))
        self.assertTrue(self.check()['ok'])

    def test_the_beat_entry_names_a_registered_task(self):
        from morph.celery import app

        app.loader.import_default_modules()
        entry = app.conf.beat_schedule['markets:fetch_exchange_rates']
        self.assertEqual(entry['task'], 'markets.fetch_exchange_rates')
        self.assertIn(entry['task'], app.tasks)
