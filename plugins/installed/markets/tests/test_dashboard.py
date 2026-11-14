"""The markets dashboard: forms through save_market, rates, preview, permissions."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.template.loader import get_template
from django.test import TestCase, override_settings
from django.urls import reverse
from djmoney.money import Money

from core.models import ExchangeRate
from plugins.installed.markets.models import Market


def _user(staff, name='u'):
    u = get_user_model().objects.create_user(username=name, email=f'{name}@x.test', password='pw')
    u.is_staff = staff
    u.save(update_fields=['is_staff'])
    return u


@override_settings(STORE_CURRENCY='USD')
class BoundaryTests(TestCase):
    """Anonymous blocked, signed in without staff blocked, staff allowed."""

    def setUp(self):
        self.market = Market.objects.create(code='us', label='US', currency='USD')
        self.staff = _user(True, 'staff')
        self.visitor = _user(False, 'visitor')
        mid = self.market.pk
        self.gets = [
            reverse('markets:index'),
            reverse('markets:create'),
            reverse('markets:edit', args=[mid]),
        ]
        self.posts = [
            reverse('markets:create'),
            reverse('markets:edit', args=[mid]),
            reverse('markets:delete', args=[mid]),
            reverse('markets:rate', args=[mid]),
            reverse('markets:rates_refresh'),
        ]

    def _refused(self, response):
        self.assertIn(response.status_code, (302, 403))
        if response.status_code == 302:
            self.assertIn('login', response['Location'])

    def test_anonymous_is_sent_to_sign_in(self):
        for url in self.gets:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn('login', r['Location'])
        for url in self.posts:
            r = self.client.post(url, {})
            self.assertEqual(r.status_code, 302, url)
            self.assertIn('login', r['Location'])
        self.assertTrue(Market.objects.filter(pk=self.market.pk).exists())

    def test_signed_in_without_staff_is_refused(self):
        self.client.force_login(self.visitor)
        for url in self.gets:
            self._refused(self.client.get(url))
        for url in self.posts:
            self._refused(self.client.post(url, {}))
        self.assertTrue(Market.objects.filter(pk=self.market.pk).exists())

    def test_staff_without_catalog_write_is_refused_a_post_when_roles_are_enforced(self):
        from plugins.registry import app_registry

        plugin = app_registry.get('rbac')
        plugin.set_config('enforcement_mode', 'enforce')
        plugin.invalidate_config_cache()

        def restore():
            plugin.set_config('enforcement_mode', 'log')
            plugin.invalidate_config_cache()

        self.addCleanup(restore)
        self.client.force_login(self.staff)
        for url in self.posts:
            self.assertEqual(self.client.post(url, {}).status_code, 403, url)
        self.assertTrue(Market.objects.filter(pk=self.market.pk).exists())

    def test_staff_is_allowed(self):
        self.client.force_login(self.staff)
        for url in self.gets:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.post(self.posts[3], {'rate': ''}).status_code, 302)

    def test_delete_asks_to_be_posted(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.posts[2]).status_code, 405)
        self.assertTrue(Market.objects.filter(pk=self.market.pk).exists())
        self.client.post(self.posts[2])
        self.assertFalse(Market.objects.filter(pk=self.market.pk).exists())


@override_settings(STORE_CURRENCY='USD')
class FormTests(TestCase):
    def setUp(self):
        self.client.force_login(_user(True))
        ExchangeRate.objects.create(
            base_currency='USD', quote_currency='EUR', rate=Decimal('0.92'), source='ecb'
        )

    def _post(self, **extra):
        data = {
            'code': 'eu',
            'label': 'Europe',
            'currency': 'EUR',
            'default_locale': 'en',
            'country_codes': 'DE, FR',
            'base_price_adjustment_pct': '0',
            'rounding': 'whole',
            'is_active': 'on',
            **extra,
        }
        return self.client.post(reverse('markets:create'), data)

    def test_create_goes_through_save_market(self):
        r = self._post()
        market = Market.objects.get(code='eu')
        self.assertRedirects(r, reverse('markets:edit', args=[market.pk]))
        self.assertEqual(market.rounding, 'whole')
        self.assertEqual(market.country_codes, ['DE', 'FR'])

    def test_a_refusal_is_shown_and_keeps_the_input(self):
        r = self._post(currency='JPY', label='Japan', code='jp')
        self.assertEqual(r.status_code, 200)
        text = ' '.join(str(m) for m in get_messages(r.wsgi_request))
        self.assertIn('Add an exchange rate for JPY first.', text)
        self.assertIn('Save the market switched off first', text)
        self.assertContains(r, 'value="Japan"')
        self.assertFalse(Market.objects.filter(code='jp').exists())

    def test_a_refused_create_keeps_every_field(self):
        r = self._post(currency='JPY', code='jp', label='Japan', is_default='on')
        self.assertContains(r, 'value="jp"')
        self.assertRegex(r.content.decode(), r'name="is_default"\s+checked')
        self.assertContains(r, '<option value="JPY" selected>')

    def test_the_new_form_preselects_the_store_currency(self):
        r = self.client.get(reverse('markets:create'))
        self.assertContains(r, '<option value="USD" selected>')

    def test_a_comma_adjustment_is_accepted(self):
        self._post(base_price_adjustment_pct='7,5')
        self.assertEqual(Market.objects.get(code='eu').base_price_adjustment_pct, Decimal('7.50'))

    def test_the_form_offers_currencies_and_roundings_as_selects(self):
        r = self.client.get(reverse('markets:create'))
        self.assertContains(r, '<select name="currency"')
        self.assertContains(r, 'EUR — Euro')
        self.assertContains(r, '<select name="rounding"')
        self.assertContains(r, 'Ends in .99')

    def test_edit_keeps_the_code(self):
        self._post()
        market = Market.objects.get(code='eu')
        self.client.post(
            reverse('markets:edit', args=[market.pk]),
            {'code': 'other', 'label': 'EU', 'currency': 'EUR', 'is_active': 'on'},
        )
        market.refresh_from_db()
        self.assertEqual((market.code, market.label), ('eu', 'EU'))


@override_settings(STORE_CURRENCY='USD')
class RateAndPreviewTests(TestCase):
    def setUp(self):
        self.client.force_login(_user(True))
        self.market = Market.objects.create(code='eu', label='Europe', currency='EUR')

    def _product(self, name='Mug', price='10.00', status='active'):
        from plugins.installed.catalog.models import Product

        return Product.objects.create(
            name=name,
            slug=name.lower(),
            sku=name.upper(),
            price=Money(Decimal(price), 'USD'),
            status=status,
        )

    def test_without_a_rate_the_page_says_so_and_previews_no_rate(self):
        self._product()
        r = self.client.get(reverse('markets:edit', args=[self.market.pk]))
        self.assertContains(r, 'No rate for EUR yet.')
        self.assertContains(r, 'No rate</span>')
        self.assertContains(r, 'Mug')

    def test_with_a_rate_the_preview_converts(self):
        self._product()
        ExchangeRate.objects.create(
            base_currency='USD', quote_currency='EUR', rate=Decimal('0.92'), source='ecb'
        )
        r = self.client.get(reverse('markets:edit', args=[self.market.pk]))
        self.assertContains(r, '1 USD = 0.92 EUR')
        self.assertContains(r, 'European Central Bank')
        self.assertContains(r, '9.20')

    def test_only_active_products_are_previewed(self):
        self._product('Visible')
        self._product('Hidden', status='draft')
        r = self.client.get(reverse('markets:edit', args=[self.market.pk]))
        self.assertContains(r, 'Visible')
        self.assertNotContains(r, 'Hidden')

    def test_the_store_currency_market_needs_no_rate(self):
        usd = Market.objects.create(code='us', label='US', currency='USD')
        r = self.client.get(reverse('markets:edit', args=[usd.pk]))
        self.assertContains(r, 'no rate is needed')

    def test_set_and_clear_a_manual_rate(self):
        url = reverse('markets:rate', args=[self.market.pk])
        self.client.post(url, {'rate': '0.9'})
        row = ExchangeRate.objects.get(quote_currency='EUR')
        self.assertEqual((row.rate, row.source), (Decimal('0.90000000'), 'manual'))
        # The EUR market is active and the daily rate cannot be fetched: yours stays.
        with mock.patch('plugins.installed.markets.rates.fetch_ecb', side_effect=OSError('x')):
            self.client.post(url, {'rate': ''})
        self.assertEqual(ExchangeRate.objects.get(quote_currency='EUR').source, 'manual')
        # Switched off, nothing needs it, so it is removed.
        Market.objects.update(is_active=False)
        self.client.post(url, {'rate': ''})
        self.assertFalse(ExchangeRate.objects.filter(quote_currency='EUR').exists())

    def test_a_bad_rate_is_refused_with_a_message(self):
        url = reverse('markets:rate', args=[self.market.pk])
        for raw, text in (('x', 'The rate must be a number.'), ('-1', 'more than zero')):
            r = self.client.post(url, {'rate': raw})
            self.assertIn(text, ' '.join(str(m) for m in get_messages(r.wsgi_request)))

    def test_refresh_reports_success_and_failure(self):
        url = reverse('markets:rates_refresh')
        with mock.patch(
            'plugins.installed.markets.rates.fetch_ecb',
            return_value={'written': 30, 'kept_manual': ['CHF'], 'date': '2026-11-13'},
        ):
            r = self.client.post(url)
        text = ' '.join(str(m) for m in get_messages(r.wsgi_request))
        self.assertIn('Fetched 30 exchange rates dated 2026-11-13.', text)
        self.assertIn('Kept your own rate for CHF.', text)
        with mock.patch(
            'plugins.installed.markets.rates.fetch_ecb', side_effect=ValueError('boom')
        ):
            r = self.client.post(url)
        text = ' '.join(str(m) for m in get_messages(r.wsgi_request))
        self.assertIn('Could not fetch the rates just now: boom', text)

    def test_a_free_product_previews_zero_not_no_rate(self):
        self._product('Freebie', price='0.00')
        ExchangeRate.objects.create(
            base_currency='USD', quote_currency='EUR', rate=Decimal('0.92'), source='ecb'
        )
        r = self.client.get(reverse('markets:edit', args=[self.market.pk]))
        self.assertContains(r, 'Freebie')
        self.assertNotContains(r, 'No rate</span>')

    def test_clearing_a_rate_nothing_replaces_is_refused_and_says_so(self):
        ExchangeRate.objects.create(
            base_currency='USD', quote_currency='EUR', rate=Decimal('0.9'), source='manual'
        )
        with mock.patch('plugins.installed.markets.rates.fetch_ecb', side_effect=OSError('x')):
            r = self.client.post(reverse('markets:rate', args=[self.market.pk]), {'rate': ''})
        self.assertIn('Your rate stays', ' '.join(str(m) for m in get_messages(r.wsgi_request)))
        self.assertTrue(ExchangeRate.objects.filter(source='manual').exists())

    def test_a_comma_rate_is_accepted(self):
        self.client.post(reverse('markets:rate', args=[self.market.pk]), {'rate': '0,9'})
        self.assertEqual(ExchangeRate.objects.get().rate, Decimal('0.9'))

    def test_rates_by_hand_hides_fetch_and_refuses_it(self):
        with mock.patch('plugins.installed.markets.views.rate_source', return_value='manual'):
            page = self.client.get(reverse('markets:edit', args=[self.market.pk]))
            self.assertNotContains(page, 'Fetch rates now')
            self.assertContains(page, 'typed by hand')
            with mock.patch('plugins.installed.markets.rates.fetch_ecb') as fetch:
                r = self.client.post(reverse('markets:rates_refresh'))
        fetch.assert_not_called()
        self.assertIn('set by hand', ' '.join(str(m) for m in get_messages(r.wsgi_request)))

    def test_the_list_shows_each_rate_status(self):
        Market.objects.create(code='us', label='US', currency='USD')
        r = self.client.get(reverse('markets:index'))
        self.assertContains(r, 'No rate')
        self.assertContains(r, 'Store currency')
        ExchangeRate.objects.create(
            base_currency='USD', quote_currency='EUR', rate=Decimal('0.92'), source='manual'
        )
        r = self.client.get(reverse('markets:index'))
        self.assertContains(r, '1 USD = 0.92')


class TemplatesCompileTests(TestCase):
    def test_every_template_compiles(self):
        for name in ('markets/list.html', 'markets/edit.html'):
            get_template(name)
