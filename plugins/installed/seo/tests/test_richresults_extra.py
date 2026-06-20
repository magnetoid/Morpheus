"""Product `extra` enrichments, VideoObject, and Organization contact/address."""

from datetime import UTC, datetime

from django.test import TestCase

from plugins.installed.seo.services.jsonld import product_jsonld, video_jsonld


class ProductExtraTests(TestCase):
    """The `extra` merge that lets the dict path emit stars/image/brand/review."""

    def _base(self, extra=None):
        return product_jsonld(
            {'slug': 'utopia', 'name': 'Utopia', 'sku': 'BK-1'},
            base_url='https://shop.test/',
            extra=extra,
        )

    def test_aggregate_rating_and_review(self):
        out = self._base(
            {
                'aggregate_rating': {'value': 4.5, 'count': 12},
                'reviews': [
                    {
                        'rating': 5,
                        'author': 'A. Reader',
                        'body': 'Loved it.',
                        'date': datetime(2026, 6, 1, tzinfo=UTC),
                    }
                ],
            }
        )
        self.assertEqual(out['aggregateRating']['@type'], 'AggregateRating')
        self.assertEqual(out['aggregateRating']['ratingValue'], '4.5')
        self.assertEqual(out['aggregateRating']['reviewCount'], 12)
        rev = out['review'][0]
        self.assertEqual(rev['@type'], 'Review')
        self.assertEqual(rev['reviewRating']['ratingValue'], '5')
        self.assertEqual(rev['author']['name'], 'A. Reader')
        self.assertEqual(rev['reviewBody'], 'Loved it.')
        self.assertEqual(rev['datePublished'], '2026-06-01T00:00:00+00:00')

    def test_image_absolutised_and_brand(self):
        out = self._base({'image': '/media/products/utopia.png', 'brand': 'Penguin'})
        self.assertEqual(out['image'], 'https://shop.test/media/products/utopia.png')
        self.assertEqual(out['brand'], {'@type': 'Brand', 'name': 'Penguin'})

    def test_no_extra_unchanged(self):
        out = self._base(None)
        self.assertNotIn('aggregateRating', out)
        self.assertNotIn('review', out)

    def test_rating_without_count_skipped(self):
        out = self._base({'aggregate_rating': {'value': 4.0, 'count': 0}})
        self.assertNotIn('aggregateRating', out)


class VideoJsonldTests(TestCase):
    def test_valid_video(self):
        blocks = video_jsonld(
            [
                {
                    'name': 'Inside Utopia',
                    'description': 'A short tour.',
                    'thumbnail_url': 'https://shop.test/p.jpg',
                    'upload_date': datetime(2026, 6, 1, tzinfo=UTC),
                    'content_url': 'https://shop.test/v.mp4',
                }
            ]
        )
        self.assertEqual(len(blocks), 1)
        b = blocks[0]
        self.assertEqual(b['@type'], 'VideoObject')
        self.assertEqual(b['thumbnailUrl'], 'https://shop.test/p.jpg')
        self.assertEqual(b['uploadDate'], '2026-06-01T00:00:00+00:00')
        self.assertEqual(b['contentUrl'], 'https://shop.test/v.mp4')

    def test_missing_required_skipped(self):
        # No thumbnail / no uploadDate → not emitted (would be invalid).
        self.assertEqual(video_jsonld([{'name': 'x', 'description': 'y'}]), [])


class OrganizationContactTests(TestCase):
    def test_contactpoint_and_address(self):
        from plugins.installed.seo.models import SiteSeoSettings
        from plugins.installed.seo.services.jsonld import organization_jsonld

        SiteSeoSettings.objects.all().delete()
        SiteSeoSettings.objects.create(organization_name='Dot Books')

        from unittest.mock import patch

        cfg = {
            'org_email': 'hi@dotbooks.store',
            'org_phone': '+1-800-555-0199',
            'org_street': '1 Shelf Ln',
            'org_city': 'Portland',
            'org_region': 'OR',
            'org_postal': '97201',
            'org_country': 'US',
        }
        with patch('plugins.installed.seo.services.jsonld._seo_plugin_cfg', return_value=cfg):
            out = organization_jsonld()
        self.assertEqual(out['contactPoint']['email'], 'hi@dotbooks.store')
        self.assertEqual(out['contactPoint']['telephone'], '+1-800-555-0199')
        self.assertEqual(out['address']['@type'], 'PostalAddress')
        self.assertEqual(out['address']['addressLocality'], 'Portland')
        self.assertEqual(out['address']['addressCountry'], 'US')
