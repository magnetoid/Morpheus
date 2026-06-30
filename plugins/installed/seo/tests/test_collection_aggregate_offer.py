"""AggregateOffer (price range) on CollectionPage JSON-LD — Google + AI Overviews
reward "Books from $5–$30" signals on category pages."""

from django.test import SimpleTestCase

from plugins.installed.seo.services import aggregate_offer, collection_page_jsonld


class AggregateOfferTests(SimpleTestCase):
    def test_builds_low_high_from_prices(self):
        out = aggregate_offer([12, 5, 30.5, 8], 'usd')
        self.assertEqual(out['@type'], 'AggregateOffer')
        self.assertEqual(out['lowPrice'], 5.0)
        self.assertEqual(out['highPrice'], 30.5)
        self.assertEqual(out['priceCurrency'], 'USD')
        self.assertEqual(out['offerCount'], 4)

    def test_skips_bad_and_nonpositive_values(self):
        out = aggregate_offer([None, 'abc', 0, -3, 10], 'EUR')
        self.assertEqual(out['lowPrice'], 10.0)
        self.assertEqual(out['highPrice'], 10.0)
        self.assertEqual(out['offerCount'], 1)

    def test_none_when_no_prices(self):
        self.assertIsNone(aggregate_offer([], 'USD'))
        self.assertIsNone(aggregate_offer([None, 'x'], 'USD'))

    def test_explicit_count_overrides(self):
        out = aggregate_offer([5, 9], 'USD', count=240)
        self.assertEqual(out['offerCount'], 240)


class CollectionPageOffersTests(SimpleTestCase):
    def test_offers_included_when_provided(self):
        offers = aggregate_offer([5, 30], 'USD')
        obj = collection_page_jsonld(
            name='Sci-Fi',
            url='/c/scifi',
            description='',
            items=[{'name': 'A', 'url': '/a'}],
            offers=offers,
        )
        self.assertEqual(obj['offers']['@type'], 'AggregateOffer')
        self.assertEqual(obj['offers']['lowPrice'], 5.0)

    def test_no_offers_key_when_absent(self):
        obj = collection_page_jsonld(
            name='Sci-Fi',
            url='/c/scifi',
            description='',
            items=[{'name': 'A', 'url': '/a'}],
        )
        self.assertNotIn('offers', obj)
