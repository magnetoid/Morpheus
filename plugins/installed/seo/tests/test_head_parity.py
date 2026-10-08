"""Golden parity: the SEO ``<head>`` a shopper (and Googlebot) sees must not
regress while the head pipeline moves into the kernel.

The rewrite (SEO 3.0) takes ``<title>``/canonical/robots/OG/JSON-LD away from
107 ``{% seo_* %}`` calls scattered across 60 theme templates and rebuilds them
from one core-fired filter. That is a change with the blast radius of *every
storefront page*, and the failure mode is silent: a page still renders, it just
stops being indexable, or loses its Product markup.

So: this test snapshots the SEO-relevant profile of every page type against the
CURRENT implementation and asserts it afterwards. The comparison is deliberately
asymmetric (see ``head_profile.diff_profiles``) — the new head may ADD JSON-LD
types and properties (Google's 2026 merchant-listing rules require several), but
it may not lose a title, a canonical, a robots directive, an OG tag, a JSON-LD
type or a recorded value.

Re-record after an INTENTIONAL change:

    DATABASE_URL='sqlite:///:memory:' MORPHEUS_RECORD_HEAD_PROFILES=1 \
        python manage.py test plugins.installed.seo.tests.test_head_parity

and review the diff of ``fixtures/head_profiles.json`` in the PR — a shrinking
profile is the bug this file exists to catch.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.seo.tests.head_profile import diff_profiles, head_profile

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'head_profiles.json'
RECORD = os.environ.get('MORPHEUS_RECORD_HEAD_PROFILES') == '1'

# What the v0.45.0 recording exposed, and what the kernel did about it. Each
# line was a real defect on the live storefront, found by diffing the old output
# against the new one rather than by reading the code.
#
#   * `/search/` rendered with NO `<title>` at all — the theme's title lived
#     inside the `{% block seo %}` the page overrode to force `noindex`, so
#     overriding the robots directive silently dropped the title.  → FIXED: the
#     kernel titles every page.
#   * The PDP emitted `og:type` twice (theme + page template).  → FIXED: head
#     entries are keyed, so the second write replaces the first.
#   * `WebSite` (and on category/collection pages `CollectionPage`) JSON-LD was
#     emitted twice — once site-wide, once by the page.  → FIXED: one `@graph`.
#   * Category / collection / journal titles carried the brand TWICE
#     ("Parity Category — dot books — Morpheus Store"), because views baked the
#     brand into `seo_title` and `title_template` appended it again (ADR 0007
#     says a stored title is the clean page name).  → FIXED: 20 hardcoded brand
#     suffixes removed from the views.
#   * The PDP emitted Book `ReadAction`, whose rich result Google deprecated on
#     2025-06-12, and `WebSite.potentialAction` (sitelinks search box, retired
#     2024-11-21).  → the SearchAction is gone; Book stays as entity data.
#   * `?sort=price` was fully indexable: `noindex_query_params` defaults to an
#     empty list, so only the canonical mitigated faceted URLs.  → still true;
#     the rules engine that fixes it lands in P2, and this baseline is the proof
#     it was not fixed by accident in the meantime.
BASELINE_FINDINGS = (
    'search: page had no <title> (fixed)',
    'pdp: duplicate og:type (fixed)',
    'multiple pages: duplicate WebSite / CollectionPage JSON-LD (fixed)',
    'category, collection, journal: brand appended twice (fixed)',
    'pdp: Book ReadAction + WebSite SearchAction, both deprecated by Google (removed)',
    'plp: ?sort= is indexable — pending the index-rules engine',
    # v0.48: the profile SHRANK here, deliberately. The Offer used to carry a
    # complete shippingDetails + hasMerchantReturnPolicy assembled from config
    # keys no settings screen ever wrote, so every store published the same
    # invented policy — including free shipping on everything, because the
    # threshold defaulted to the truthy string '0'. The apps that own the data
    # contribute it now, and this fixture's store has no shipping rates and no
    # store country, so it correctly claims neither.
    'pdp: fabricated free-shipping + return-policy markup (removed; owners contribute it)',
    "pdp: Product.sku published as '' because the page query never selected it (fixed)",
    # v0.80.0: the profile SHRANK again, deliberately — the noindex rule. A page
    # that asks not to be indexed no longer carries a graph, hreflang or a
    # canonical naming another URL: `/cart/` and `/search/` lost their WebSite/
    # WebPage nodes, and `/products/?q=` — internal search results, which used
    # to be fully indexable with a canonical claiming to be the catalogue — is
    # now `noindex, follow` with no canonical at all. Every graph `url`/`@id`
    # is the canonical, so `?sort=price` describes `/products/`, not itself.
    'search, cart: graph on a noindex page (removed)',
    'plp ?q=: indexable search results with a canonical naming /products/ (fixed)',
    'plp ?sort=: graph url carried the parameter the canonical drops (fixed)',
    # Also v0.80.0: private pages are titled for a person ("Your cart", not the
    # Title-Cased route name), and a vendor's breadcrumb is Home › <the theme's
    # word for vendors> › name — the "Marketplace" hop linked a landing page
    # written for one bookshop.
    'cart: title from the route name (now "Your cart")',
    'vendor: breadcrumb through the bookshop-only Marketplace landing (removed)',
)

_PRODUCT = 'head-parity-probe'
_CATEGORY = 'head-parity-category'
_COLLECTION = 'head-parity-collection'
_VENDOR = 'head-parity-press'
_JOURNAL = 'head-parity-journal-entry'
_AUTHOR = 'Ines Parityauthor'
_AUTHOR_SLUG = 'ines-parityauthor'


class HeadParityTests(TestCase):
    """One profile per page type; every storefront surface shape is covered."""

    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        from plugins.installed.book_product.models import BookProduct
        from plugins.installed.catalog.models import Category, Collection, Product, Vendor
        from plugins.installed.cms.models import Page

        cls.vendor = Vendor.objects.create(
            name='Parity Press', slug=_VENDOR, description='A press used by the parity probe.'
        )
        cls.category = Category.objects.create(
            name='Parity Category',
            slug=_CATEGORY,
            description='Books that measure themselves.',
        )
        cls.collection = Collection.objects.create(
            name='Parity Collection',
            slug=_COLLECTION,
            description='A curated shelf for the parity probe.',
        )
        cls.product = Product.objects.create(
            name='Head Parity Probe',
            slug=_PRODUCT,
            sku='HPP-1',
            price=Money(Decimal('14.00'), 'USD'),
            product_type='simple',
            status='active',
            vendor=cls.vendor,
            description=(
                'A deliberately wordy description so the thin-content heuristics do not '
                'change the robots directive between the recording run and the assertion '
                'run. It says nothing of consequence, at length, on purpose, so that the '
                'word count comfortably clears any threshold a merchant might configure.'
            ),
            short_description='A probe product used to snapshot the SEO head.',
        )
        cls.product.category = cls.category
        cls.product.save(update_fields=['category'])
        cls.collection.products.add(cls.product)
        BookProduct.objects.create(product=cls.product, author=_AUTHOR)
        Page.objects.create(
            slug=_JOURNAL,
            title='Parity journal entry',
            state='published',
            # Deliberately ancient. The journal index orders by publish date, so
            # a probe entry dated "a minute ago" lands somewhere in the middle
            # of the seeded posts depending on when the seed data was created —
            # and the recorded ItemList order then flips between runs, failing
            # the snapshot over nothing. Pinning it to the end makes the
            # position of every entry deterministic.
            publish_at=timezone.now() - timedelta(days=3650),
            body='<p>An entry that exists so the journal detail page has a subject.</p>',
            metadata={'category': 'journal'},
        )

    def setUp(self):
        cache.clear()  # a cached fragment would snapshot someone else's head

    # -- the page matrix -------------------------------------------------
    def _paths(self) -> list[str]:
        return [
            '/',
            '/products/',
            '/products/?sort=price',  # param → expected noindex, clean canonical
            f'/products/{_PRODUCT}/',
            f'/category/{_CATEGORY}/',
            f'/collection/{_COLLECTION}/',
            f'/vendor/{_VENDOR}/',
            f'/author/{_AUTHOR_SLUG}/',
            '/journal/',
            f'/journal/{_JOURNAL}/',
            '/search/',  # mood-search landing; the template forces noindex
            '/products/?q=parity',  # where a keyword search actually lands
            '/about/',
            '/contact/',
            '/cart/',  # private surface
        ]

    def _profiles(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for path in self._paths():
            response = self.client.get(path)
            body = response.content.decode() if response.status_code == 200 else ''
            out[path] = head_profile(body, path=path, status=response.status_code)
        return out

    def test_head_profiles_match_the_recorded_baseline(self):
        current = self._profiles()

        if RECORD:
            FIXTURE.parent.mkdir(parents=True, exist_ok=True)
            FIXTURE.write_text(json.dumps(current, indent=2, sort_keys=True) + '\n')
            self.skipTest(f'recorded {len(current)} head profiles to {FIXTURE}')

        self.assertTrue(
            FIXTURE.exists(),
            f'{FIXTURE} is missing — record it with MORPHEUS_RECORD_HEAD_PROFILES=1',
        )
        baseline = json.loads(FIXTURE.read_text())

        regressions: list[str] = []
        for path, before in baseline.items():
            after = current.get(path)
            if after is None:
                regressions.append(f'{path}: no longer rendered by the test matrix')
                continue
            regressions.extend(f'{path}: {problem}' for problem in diff_profiles(before, after))

        self.assertEqual(regressions, [], 'SEO head regressions:\n  ' + '\n  '.join(regressions))

    def test_every_indexable_page_has_exactly_one_title_and_canonical(self):
        """Invariant that must hold in BOTH implementations.

        The recorded baseline pins today's *values*; this pins the shape, so a
        rewrite that emits two titles (shell fallback + plugin) fails here even
        if both happen to say the same thing.
        """
        for path, profile in self._profiles().items():
            if profile['status'] != 200:
                continue
            with self.subTest(path=path):
                self.assertEqual(profile['title_count'], 1, f'{path}: <title> count')
                self.assertLessEqual(profile['canonical_count'], 1, f'{path}: canonical count')
                self.assertLessEqual(profile['robots_count'], 1, f'{path}: robots meta count')
