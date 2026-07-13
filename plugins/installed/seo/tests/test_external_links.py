"""apply_external_links — deterministic, verified external references.

Uses --no-verify-web so tests never hit the network; the Wikipedia path is
exercised only by _verify_wikipedia's own contract (type gate), not here.
"""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.metafields.models import Metafield


def _make_book(slug='dune'):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
        description='<p>A desert epic.</p>',
    )
    Metafield.objects.set(p, namespace='book', key='openlibrary', value='OL893415W')
    Metafield.objects.set(p, namespace='book', key='oclc', value='19986521')
    Metafield.objects.set(p, namespace='identifiers', key='isbn13', value='9780441172719')
    return p


class ApplyExternalLinksTests(TestCase):
    def _run(self, *args):
        out = StringIO()
        call_command('apply_external_links', '--no-verify-web', *args, stdout=out)
        return out.getvalue()

    def test_data_derived_links_written_and_survive_sanitize(self):
        p = _make_book()
        self._run('--slugs', 'dune')
        body = Product.objects.get(pk=p.pk).description
        self.assertIn('Sources', body)  # the references heading is present
        self.assertIn('openlibrary.org/works/OL893415W', body)
        self.assertIn('search.worldcat.org/title/19986521', body)
        self.assertIn('openlibrary.org/isbn/9780441172719', body)
        # rel/target survive Product.save() sanitize (core.utils.html allowlist).
        self.assertIn('target="_blank"', body)
        self.assertIn('rel="noopener"', body)

    def test_idempotent_no_duplicate_block(self):
        _make_book()
        self._run('--slugs', 'dune')
        self._run('--slugs', 'dune')  # second run must not append again
        body = Product.objects.get(slug='dune').description
        self.assertEqual(body.count('Sources'), 1)  # only one references block

    def test_book_without_identifiers_gets_no_block(self):
        Product.objects.create(
            name='Bare',
            slug='bare',
            sku='BARE',
            price=Money(Decimal('5.00'), 'USD'),
            product_type='simple',
            status='active',
            description='<p>No ids.</p>',
        )
        self._run('--slugs', 'bare')
        body = Product.objects.get(slug='bare').description
        self.assertNotIn('Sources', body)  # never invents links


class PreserveAcrossRegenerateTests(TestCase):
    def test_extract_related_reading_keeps_both_blocks(self):
        from plugins.installed.catalog.management.commands.populate_descriptions import (
            _extract_related_reading,
        )

        body = (
            '<p>Body.</p>\n<h2>Related reading</h2>\n<p>See X.</p>\n'
            '<h2>Sources and references</h2>\n<p>Refs.</p>'
        )
        kept = _extract_related_reading(body)
        self.assertIn('Related reading', kept)
        self.assertIn('Sources', kept)  # both link blocks preserved
