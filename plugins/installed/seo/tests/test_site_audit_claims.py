"""The site audit checks what the markup claims (v0.164.0).

A Product node's offer is a public statement. The audit holds it to the page (is
that price printed?) and to its owners (is it the price `core.pricing` gives now,
the stock inventory reports, an image that loads?), and reads the links between
pages for redirects, chains and pages nothing links to.

Each check gets a page that is wrong and one that is right. A "cached page" is
HTML rendered before the data changed, handed to the audit as the crawl's answer:
that is what a CDN serves for up to its TTL, and what the in-process crawl never
sees on its own.
"""

from __future__ import annotations

import json
import secrets
import shutil
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.seo.services import site_audit

HOST = 'testserver'


def _finding(report, code) -> dict | None:
    return next((f for f in report['findings'] if f['code'] == code), None)


def _codes(report) -> list[str]:
    return [f['code'] for f in report['findings']]


def _page(*, graph=(), body='', head=''):
    """A rendered page: a head with one graph, and a body."""
    block = json.dumps({'@context': 'https://schema.org', '@graph': list(graph)})
    return (
        '<!doctype html><html lang="en"><head><title>A page</title>'
        f'<script type="application/ld+json">{block}</script>{head}</head>'
        f'<body><h1>A page</h1>{body}</body></html>'
    )


def _product_node(**offer):
    return {
        '@type': 'Product',
        'name': 'Claim Probe',
        'sku': 'CP-1',
        'url': f'https://{HOST}/products/claim-probe/',
        'offers': {'@type': 'Offer', 'priceCurrency': 'USD', **offer},
    }


# The audit fetches the store's own host (site_base_url); pin it, so the crafted
# pages' absolute URLs are on the store whatever the environment's settings say.
@override_settings(SITE_BASE_URL=f'https://{HOST}')
class _AuditCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Claim Probe',
            slug='claim-probe',
            sku='CP-1',
            price=Money(Decimal('12.00'), 'USD'),
            product_type='simple',
            status='active',
            description='A description long enough not to trip the thin check. ' * 20,
        )

    def setUp(self):
        cache.clear()

    def audit(self, pages: dict[str, str | None], *, limit=None) -> dict:
        """Run the audit over exactly ``pages``: a path with HTML is served that
        HTML (a cached page); a path with None is rendered for real."""
        real_facts = site_audit._facts

        def facts(client, path, host):
            html = pages.get(path)
            if html is None:
                return real_facts(client, path, host)
            return site_audit.page_facts(path, 200, html, host)

        with (
            patch.object(site_audit, '_paths', return_value=list(pages)),
            patch.object(site_audit, '_facts', side_effect=facts),
        ):
            return site_audit.collect(limit=limit)

    def rendered(self, path: str) -> str:
        response = self.client.get(path, secure=True, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()


class PriceClaimTests(_AuditCase):
    def test_a_correct_product_page_is_quiet(self):
        report = self.audit({'/products/claim-probe/': None})
        for code in ('markup_price_not_on_page', 'markup_price_stale', 'markup_availability_wrong'):
            self.assertIsNone(_finding(report, code), report['findings'])
        # The check ran: the page's Product node was read and matched to its row.
        self.assertGreaterEqual(report['checks']['products'], 1)
        self.assertEqual(report['checks']['products_without_owner'], 0)

    def test_a_price_changed_behind_a_cached_page_is_stale(self):
        cached = self.rendered('/products/claim-probe/')
        # A queryset update skips every signal, as a bulk edit or an import does.
        Product.objects.filter(pk=self.product.pk).update(price=Money(Decimal('15.00'), 'USD'))
        report = self.audit({'/products/claim-probe/': cached})
        finding = _finding(report, 'markup_price_stale')
        self.assertIsNotNone(finding, _codes(report))
        self.assertEqual(finding['severity'], site_audit.CRITICAL)
        self.assertIn(
            '/products/claim-probe/: Claim Probe claims 12.00 USD; the price is 15.00 USD',
            finding['examples'],
        )
        # The cached page still prints the price its markup states.
        self.assertIsNone(_finding(report, 'markup_price_not_on_page'))

    def test_a_pricing_rule_is_the_price(self):
        """The owner's answer goes through PRODUCT_CALCULATE_PRICE, like the cart."""
        from core.hooks import MorpheusEvents, hook_registry

        def two_off(value, **_kw):
            return Money(value.amount - 2, value.currency)

        page = _page(graph=[_product_node(price='12.00')], body='<p>$12.00</p>')
        event = MorpheusEvents.PRODUCT_CALCULATE_PRICE
        saved = list(hook_registry._handlers[event])
        self.addCleanup(hook_registry._handlers.__setitem__, event, saved)
        hook_registry.register(event, two_off, priority=1)
        finding = _finding(self.audit({'/crafted/': page}), 'markup_price_stale')
        self.assertIsNotNone(finding)
        self.assertIn('claims 12.00 USD; the price is 10.00 USD', finding['examples'][0])

    def test_a_price_only_the_markup_carries_is_reported(self):
        hidden = _page(graph=[_product_node(price='12.00')], body='<p>Ask us for a price.</p>')
        shown = _page(graph=[_product_node(price='12.00')], body='<p>Now <b>$12.00</b></p>')
        in_a_script = _page(
            graph=[_product_node(price='12.00')],
            body='<p>Ask us.</p><script>var price = "$12.00";</script>',
        )
        report = self.audit({'/hidden/': hidden, '/shown/': shown, '/in-a-script/': in_a_script})
        finding = _finding(report, 'markup_price_not_on_page')
        self.assertIsNotNone(finding, _codes(report))
        self.assertEqual(
            sorted(finding['examples']),
            [
                '/hidden/: Claim Probe claims 12.00 USD; the page shows no such price',
                '/in-a-script/: Claim Probe claims 12.00 USD; the page shows no such price',
            ],
        )

    def test_a_larger_number_ending_in_the_price_does_not_count(self):
        page = _page(graph=[_product_node(price='12.00')], body='<p>$112.00</p>')
        self.assertIsNotNone(
            _finding(self.audit({'/x/': page}), 'markup_price_not_on_page'),
            '112.00 is not 12.00',
        )


class AvailabilityClaimTests(_AuditCase):
    def setUp(self):
        super().setUp()
        from plugins.installed.catalog.variants import ensure_stock_variant
        from plugins.installed.inventory.services import InventoryService, create_warehouse

        self.variant = ensure_stock_variant(self.product)
        self.warehouse = create_warehouse('Main', 'MAIN', make_default=True)
        InventoryService.set_quantity(self.variant, self.warehouse, 5)

    def test_stock_that_sold_out_behind_a_cached_page_is_reported(self):
        from plugins.installed.inventory.services import InventoryService

        cached = self.rendered('/products/claim-probe/')
        self.assertIn('https://schema.org/InStock', cached)
        InventoryService.set_quantity(self.variant, self.warehouse, 0)
        report = self.audit({'/products/claim-probe/': cached})
        finding = _finding(report, 'markup_availability_wrong')
        self.assertIsNotNone(finding, _codes(report))
        self.assertEqual(
            finding['examples'],
            ['/products/claim-probe/: claims instock; inventory says outofstock'],
        )

    def test_a_page_rendered_now_agrees_with_inventory(self):
        from plugins.installed.inventory.services import InventoryService

        InventoryService.set_quantity(self.variant, self.warehouse, 0)
        report = self.audit({'/products/claim-probe/': None})
        self.assertIsNone(_finding(report, 'markup_availability_wrong'), report['findings'])
        self.assertEqual(report['checks']['products_without_owner'], 0)


class ImageClaimTests(_AuditCase):
    def setUp(self):
        super().setUp()
        from PIL import Image

        folder = f'seo-audit-test-{secrets.token_hex(4)}'
        root = Path(settings.MEDIA_ROOT) / folder
        root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, root, True)
        Image.new('RGB', (100, 50), 'white').save(root / 'good.png')
        self.good = f'/media/{folder}/good.png'
        self.missing = f'/media/{folder}/missing.png'

    def _og(self, url, size=None):
        tags = f'<meta property="og:image" content="https://{HOST}{url}">'
        if size:
            tags += (
                f'<meta property="og:image:width" content="{size[0]}">'
                f'<meta property="og:image:height" content="{size[1]}">'
            )
        return tags

    def test_an_image_that_does_not_load_is_reported(self):
        node = {**_product_node(price='12.00'), 'image': [f'https://{HOST}{self.missing}']}
        page = _page(graph=[node], body='<p>$12.00</p>', head=self._og(self.good))
        finding = _finding(self.audit({'/x/': page}), 'markup_image_broken')
        self.assertIsNotNone(finding)
        self.assertEqual(len(finding['examples']), 1)
        # The media view's 404 is text/plain here; any non-image answer counts.
        self.assertTrue(
            finding['examples'][0].startswith(f'/x/: https://{HOST}{self.missing} answers 404 '),
            finding['examples'],
        )

    def test_images_that_load_and_off_host_images_are_quiet(self):
        node = {
            **_product_node(price='12.00'),
            'image': [f'https://{HOST}{self.good}', 'https://upload.wikimedia.org/a/b.jpg'],
        }
        page = _page(graph=[node], body='<p>$12.00</p>', head=self._og(self.good))
        report = self.audit({'/x/': page})
        self.assertIsNone(_finding(report, 'markup_image_broken'), report['findings'])
        self.assertEqual(report['checks']['images'], 1)  # fetched once for both claims
        self.assertEqual(report['checks']['images_off_host'], 1)

    def test_a_static_image_counts_by_the_file_in_the_build(self):
        # Nothing serves /static/ under the test runner, as nginx or a CDN may
        # serve it elsewhere: a file the build holds is fine, a missing one is not.
        shipped = _page(head=self._og('/static/pwa/icon-192.png'))
        missing = _page(head=self._og('/static/pwa/no-such-icon.png'))
        finding = _finding(self.audit({'/a/': shipped, '/b/': missing}), 'markup_image_broken')
        self.assertIsNotNone(finding)
        self.assertEqual(len(finding['examples']), 1)
        self.assertTrue(finding['examples'][0].startswith('/b/: '), finding['examples'])

    def test_a_declared_size_the_file_does_not_have_is_reported(self):
        wrong = _page(head=self._og(self.good, (1200, 630)))
        right = _page(head=self._og(self.good, (100, 50)))
        report = self.audit({'/wrong/': wrong, '/right/': right})
        finding = _finding(report, 'og_image_size_wrong')
        self.assertIsNotNone(finding, _codes(report))
        self.assertEqual(finding['severity'], site_audit.WARNING)
        self.assertEqual(finding['examples'], ['/wrong/: declares 1200×630, the file is 100×50'])


class LinkTests(_AuditCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from plugins.installed.seo.models import Redirect

        # One hop, and a chain of two: /chain-1/ is saved before /chain-2/ exists,
        # so collapse_chain (which follows a rule's own target on save) keeps it.
        Redirect.objects.create(from_path='/old-a/', to_path='/products/claim-probe/')
        Redirect.objects.create(from_path='/chain-1/', to_path='/chain-2/')
        Redirect.objects.create(from_path='/chain-2/', to_path='/products/claim-probe/')

    def test_a_link_to_a_redirect_and_a_chain_are_reported(self):
        page = _page(
            body=(
                '<a href="/old-a/">old</a> <a href="/chain-1/">chain</a> '
                '<a href="/products/claim-probe/">direct</a>'
            )
        )
        report = self.audit({'/from/': page, '/products/claim-probe/': None})
        one = _finding(report, 'link_to_redirect')
        self.assertIsNotNone(one, _codes(report))
        self.assertEqual(one['examples'], ['/from/ links to /old-a/ → /products/claim-probe/'])
        chain = _finding(report, 'redirect_chain')
        self.assertIsNotNone(chain, _codes(report))
        self.assertEqual(chain['severity'], site_audit.CRITICAL)
        self.assertEqual(
            chain['examples'],
            ['/from/ links to /chain-1/ → /chain-2/ → /products/claim-probe/ (2 hops)'],
        )

    def test_direct_links_and_switchers_are_quiet(self):
        """The real product page links to the affiliate and vendor sign-ups, which
        send an anonymous visitor to sign in: a door, never a finding."""
        page = _page(
            body=(
                '<a href="/products/claim-probe/">direct</a>'
                '<a href="/old-a/" hreflang="sr">Srpski</a>'
                '<a href="/chain-1/" rel="nofollow">x</a>'
                '<a href="mailto:a@b.c">mail</a> <a href="https://elsewhere.example/old-a/">x</a>'
            )
        )
        report = self.audit({'/from/': page, '/products/claim-probe/': None})
        self.assertIsNone(_finding(report, 'link_to_redirect'), report['findings'])
        self.assertIsNone(_finding(report, 'redirect_chain'), report['findings'])


class OrphanTests(_AuditCase):
    def _pages(self, *, a_links_c: bool) -> dict[str, str]:
        return {
            '/a/': _page(body='<a href="/b/">b</a>' + ('<a href="/c/">c</a>' if a_links_c else '')),
            '/b/': _page(body='<a href="/a/">a</a><a href="/b/">myself</a>'),
            '/c/': _page(body='<a href="/a/">a</a><a href="/c/">myself</a>'),
        }

    def test_a_sitemap_page_nothing_links_to_is_an_orphan(self):
        report = self.audit(self._pages(a_links_c=False))
        self.assertTrue(report['checks']['orphans_checked'])
        finding = _finding(report, 'orphan_page')
        self.assertIsNotNone(finding, _codes(report))
        self.assertEqual(finding['severity'], site_audit.NOTICE)
        self.assertEqual(finding['examples'], ['/c/'])  # a link to itself does not count

    def test_a_linked_page_is_not(self):
        report = self.audit(self._pages(a_links_c=True))
        self.assertIsNone(_finding(report, 'orphan_page'), report['findings'])

    def test_a_partial_crawl_names_no_orphans_and_says_why(self):
        report = self.audit(self._pages(a_links_c=False), limit=2)
        self.assertIsNone(_finding(report, 'orphan_page'), report['findings'])
        self.assertFalse(report['checks']['orphans_checked'])
        self.assertEqual(
            report['checks']['orphans_skipped_because'], 'the scan read 2 of 3 sitemap URLs'
        )

    def test_a_page_linked_only_from_a_later_listing_page_is_not_an_orphan(self):
        """A product on page 2 of a category is linked from page 2 (rel=next)."""
        pages = self._pages(a_links_c=False)
        pages['/a/'] = _page(head='<link rel="next" href="/a/?page=2">', body='<a href="/b/">b</a>')
        page_two = _page(body='<a href="/c/">c</a>')
        real = site_audit._facts

        def facts(client, path, host):
            if path == '/a/?page=2':
                return site_audit.page_facts(path, 200, page_two, host)
            return real(client, path, host)

        with patch.object(site_audit, '_facts', side_effect=facts):
            # `audit` wraps the patched _facts again for the sitemap pages.
            report = self.audit(pages)
        self.assertIsNone(_finding(report, 'orphan_page'), report['findings'])
        self.assertEqual(report['checks']['pagination_fetches'], 1)


class MeasuredTests(_AuditCase):
    def test_the_report_says_what_was_measured(self):
        report = self.audit({'/products/claim-probe/': None})
        for key in ('crawl_s', 'claims_s', 'links_s', 'total_s'):
            self.assertIn(key, report['measured'])
        self.assertLess(report['measured']['total_s'], site_audit.EXTRA_DEADLINE_S)
        self.assertEqual(report['checks']['capped'], [])


class EveryThemeIsQuietTests(_AuditCase):
    """A product page rendered now, under every contract theme, raises no claim
    finding: each theme prints the price its markup states (a grouped one too),
    and the audit finds the row each claim speaks for."""

    def test_a_fresh_product_page_is_quiet_under_every_theme(self):
        from themes.test_head_contract import _activate_theme, _contract_themes

        Product.objects.create(
            name='Grouped Probe',
            slug='grouped-probe',
            sku='GP-1',
            price=Money(Decimal('1234.50'), 'USD'),
            product_type='simple',
            status='active',
        )
        themes = _contract_themes()
        self.assertTrue(themes)
        for name in themes:
            with self.subTest(theme=name):
                _activate_theme(self, name)
                # A store runs with its own theme's static folder (STATICFILES_DIRS
                # follows MORPHEUS_ACTIVE_THEME); switching at runtime keeps the
                # default theme's, so the travel themes' og-default.jpg was "missing".
                base = Path(settings.BASE_DIR)
                folders = [base / 'static', base / 'themes' / 'library' / name / 'static']
                with override_settings(STATICFILES_DIRS=[d for d in folders if d.exists()]):
                    report = self.audit(
                        {'/products/claim-probe/': None, '/products/grouped-probe/': None}
                    )
                for code in (
                    'markup_price_not_on_page',
                    'markup_price_stale',
                    'markup_availability_wrong',
                    'markup_image_broken',
                    'og_image_size_wrong',
                ):
                    self.assertIsNone(_finding(report, code), f'{name}: {_finding(report, code)}')
                self.assertGreaterEqual(report['checks']['products'], 2, name)
                self.assertEqual(report['checks']['products_without_owner'], 0, name)
