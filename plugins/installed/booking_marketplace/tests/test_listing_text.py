"""A listing's text comes from its Product's rich text, and every surface reads it right.

The product editor saves descriptions as sanitised HTML (`<p>`, `<strong>`, `&amp;`).
The listing keeps a copy that feeds, structured data, llms.txt and the host's form
read as plain text, and the booking page printed it escaped: an edit in the product
editor would have put literal `<p>` tags on the page and in every feed.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.products import ensure_product, sync_from_product
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor

RICH = (
    '<p>Paddle <strong>past the walls</strong> at dawn.</p>'
    '<p>Kotor &amp; Perast by water.</p>'
    '<ul><li>Kayak</li><li>Life vest</li></ul>'
)


class ListingTextTests(TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            short_description='Paddle the bay.',
            description='Paddle the bay.',
        )
        self.product = ensure_product(self.svc)

    def _edit_product(self, **fields):
        for name, value in fields.items():
            setattr(self.product, name, value)
        self.product.save()
        sync_from_product(self.product)
        self.svc.refresh_from_db()

    def _page(self):
        return self.client.get(f'/bookings/{self.svc.slug}/').content.decode()

    def test_the_listing_copy_is_plain_text(self):
        self._edit_product(description=RICH, short_description='<p>Kotor &amp; Perast at dawn.</p>')
        self.assertEqual(
            self.svc.description,
            'Paddle past the walls at dawn.\n\nKotor & Perast by water.\n\n• Kayak\n• Life vest',
        )
        self.assertEqual(self.svc.short_description, 'Kotor & Perast at dawn.')

    def test_saving_the_listing_keeps_the_products_formatting(self):
        # A host changes the price; the text they did not touch keeps its formatting.
        from plugins.installed.booking_marketplace.products import save_listing

        self._edit_product(description=RICH)
        self.svc.price = Money(Decimal('60'), 'EUR')
        save_listing(self.svc)
        self.product.refresh_from_db()
        self.assertEqual(self.product.description, RICH)
        self.assertEqual(self.product.price.amount, Decimal('60'))

    def test_a_hosts_text_edit_reaches_the_product(self):
        from plugins.installed.booking_marketplace.products import save_listing

        self._edit_product(description=RICH)
        self.svc.description = 'A new plan for the morning.'
        save_listing(self.svc)
        self.product.refresh_from_db()
        self.assertEqual(self.product.description, 'A new plan for the morning.')

    def test_the_booking_page_shows_the_products_formatting(self):
        self._edit_product(description=RICH)
        html = self._page()
        self.assertIn('<strong>past the walls</strong>', html)
        self.assertIn('<li>Life vest</li>', html)
        self.assertNotIn('&lt;p&gt;', html)

    def test_text_without_tags_renders_as_paragraphs(self):
        # A host's plain text, saved through the product's sanitiser (`&` → `&amp;`).
        self._edit_product(description='One&amp;Only spa.\n\nA second paragraph.')
        html = self._page()
        self.assertIn('One&amp;Only spa.', html)
        self.assertNotIn('&amp;amp;', html)
        self.assertIn('<p>A second paragraph.</p>', html)

    def test_a_long_product_name_and_summary_fit_the_listing(self):
        # Product.name allows 300 characters and short_description is unlimited; the
        # listing's copies are varchar(200) and varchar(300), and Postgres refuses more.
        self._edit_product(
            name='Kayak the bay of Kotor ' * 11,
            short_description='<p>' + 'Paddle under the walls at dawn. ' * 15 + '</p>',
        )
        self.assertLessEqual(len(self.svc.name), 200)
        self.assertLessEqual(len(self.svc.short_description), 300)
        self.assertTrue(self.svc.short_description.endswith('…'))

    def test_saving_the_listing_keeps_the_products_long_text(self):
        from plugins.installed.booking_marketplace.products import save_listing

        long_name = ('Kayak the bay of Kotor ' * 11).strip()
        long_summary = 'Paddle under the walls at dawn. ' * 15
        self._edit_product(name=long_name, short_description=long_summary)
        self.svc.price = Money(Decimal('60'), 'EUR')
        save_listing(self.svc)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, long_name)
        self.assertEqual(self.product.short_description, long_summary)

    def test_a_browser_post_of_unchanged_text_keeps_the_formatting(self):
        # Browsers post a textarea's line breaks as CRLF and drop newlines from a
        # single-line input: text the host did not touch must still read as unchanged.
        from plugins.installed.booking_marketplace.products import save_listing

        summary = '<p>Kotor at dawn.</p><p>By water.</p>'
        self._edit_product(description=RICH, short_description=summary)
        self.svc.description = self.svc.description.replace('\n', '\r\n')
        self.svc.short_description = self.svc.short_description.replace('\n', '')
        self.svc.price = Money(Decimal('60'), 'EUR')
        save_listing(self.svc)
        self.product.refresh_from_db()
        self.assertEqual(self.product.description, RICH)
        self.assertEqual(self.product.short_description, summary)


class MontenegroListingTextTests(MontenegroThemeMixin, ListingTextTests):
    """The Montenegro theme renders the booking page itself."""
