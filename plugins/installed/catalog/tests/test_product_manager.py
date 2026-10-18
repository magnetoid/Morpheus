"""Product's manager carries django-money's wrapping once, from start-up on.

django-money wraps the `objects` manager of every model with a MoneyField when
the class is prepared, so `price=Money(10, 'EUR')` matches the amount AND the
currency. Django has copied the manager by then, so that wrapping only reaches
`Product.objects` once something refreshes the model cache, which is why v0.109.0
wrapped it a second time by hand. After a refresh both wrappings were live, and
Django 6.1 filters a related manager's queryset in place, so each filter stacked
one wrapper per wrapping and the third broke django-money: `'function' object has
no attribute '__self__'`. A refresh happens whenever a model class is created
after start-up; on Supernatural and Irving, the first import of the book app's
models (a store without it still imports them). From then on the staff-picks
check in the storefront's sitemap contribution raised, and the sitemaps left out
the shop's index and content pages: /products/, /about/, /journal/ and the rest
(90 errors between 2026-10-14 and v0.115.1).
"""

from __future__ import annotations

import os
import subprocess
import sys
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Collection, Product


def refresh_model_cache():
    """What Django does when a model class is created after start-up."""
    apps.clear_cache()
    # A related manager's class is built on first use, from Product's manager at
    # that moment: rebuild it the way the first use after a refresh does.
    for descriptor in (Collection.products, Category.products):
        descriptor.__dict__.pop('related_manager_cls', None)


class RefreshedModelCacheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Coffee', slug='coffee')
        cls.picks = Collection.objects.create(name='Staff picks', slug='staff-picks')
        book = Product.objects.create(
            name='Book',
            slug='book',
            sku='B1',
            status='active',
            category=cls.category,
            price=Money(Decimal('10'), 'EUR'),
        )
        Product.objects.create(
            name='Pen', slug='pen', sku='P1', status='active', price=Money(Decimal('10'), 'USD')
        )
        cls.picks.products.add(book)

    def test_related_managers_filter_after_a_refresh(self):
        refresh_model_cache()
        self.assertTrue(self.picks.products.filter(status='active').exists())
        self.assertTrue(self.category.products.filter(status='active').exists())

    def test_money_lookups_match_the_currency_after_a_refresh(self):
        refresh_model_cache()
        eur = Money(Decimal('10'), 'EUR')
        self.assertEqual(Product.objects.filter(price=eur).count(), 1)
        self.assertEqual(Product.objects.shoppable().filter(price=eur).count(), 1)
        self.assertEqual(self.picks.products.filter(price=eur).count(), 1)


_MARKER = 'MONEY-LOOKUPS:'

# Runs in a fresh interpreter: the copy Django hands out at start-up is the one
# the in-process tests can no longer see once anything has refreshed the cache.
_FRESH_PROCESS = f"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'morph.settings')
import django
django.setup()
from decimal import Decimal
from django.apps import apps
from djmoney.money import Money
from plugins.installed.catalog.models import Product
def matches_currency():
    # Only the WHERE clause can name the currency column: the query selects pk.
    query = Product.objects.filter(price=Money(Decimal('10'), 'EUR')).values('pk').query
    return 'price_currency' in str(query)
at_start_up = matches_currency()
apps.clear_cache()
print({_MARKER!r}, at_start_up, matches_currency())
"""


class FreshProcessTests(SimpleTestCase):
    def test_money_lookups_match_the_currency_from_start_up(self):
        proc = subprocess.run(  # noqa: S603 — fixed interpreter + fixed script
            [sys.executable, '-c', _FRESH_PROCESS, 'test'],
            capture_output=True,
            text=True,
            cwd=settings.BASE_DIR,
            env={**os.environ, 'DATABASE_URL': 'sqlite:///:memory:'},
            timeout=300,
            check=False,
        )
        lines = [line for line in proc.stdout.splitlines() if line.startswith(_MARKER)]
        self.assertTrue(lines, f'boot failed (rc={proc.returncode}):\n{proc.stderr[-4000:]}')
        self.assertEqual(lines[-1].split()[1:], ['True', 'True'])
