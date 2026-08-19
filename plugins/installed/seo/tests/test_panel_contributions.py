"""The SEO panel is contributed, not hardcoded — and it must not lose data.

The panel now reaches four different edit forms through four filters. Two
properties matter more than the rendering:

* **It vanishes with the app.** A surface that survives a disable was wired in
  the wrong layer (ADR 0013).
* **A form that never rendered it cannot wipe it.** `save_object_seo` gates on
  the panel's own field being present in the POST; without that, any save from
  a form without the card writes blanks over the row and flips a noindex page
  back into the index.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from plugins.installed.catalog.models import Category, Collection, Product
from plugins.installed.seo.models import SeoMeta
from plugins.installed.seo.services.panel import panel_context, save_object_seo
from plugins.registry import app_registry

MARKER = 'name="seo_title"'


def _staff():
    return get_user_model().objects.create_user(
        username='seo-panel-staff',
        email='panel@example.test',
        password='pw',
        is_staff=True,
        is_superuser=True,
    )


class PanelStorageTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Panel Probe', slug='panel-probe', sku='PP-1', price=Decimal('9.00')
        )

    def test_a_post_without_the_panel_never_touches_stored_seo(self):
        """The guard that stops a card-less form from wiping a merchant's SEO."""
        save_object_seo(self.product, {'seo_title': 'Kept', 'seo_noindex': '1'})
        self.assertEqual(SeoMeta.for_obj(self.product).title, 'Kept')

        save_object_seo(self.product, {'name': 'unrelated form post'})

        meta = SeoMeta.for_obj(self.product)
        self.assertEqual(meta.title, 'Kept')
        self.assertIn('noindex', meta.robots)

    def test_the_panel_reads_through_to_the_native_columns(self):
        """A product carrying a meta title typed before the move must show it,
        not an empty box the merchant has to retype.

        Creating a product autofills a SeoMeta row from its name, so this is
        also the autofill-vs-merchant case: the typed column has to win.
        """
        self.product.meta_title = 'Typed before v0.47'
        self.product.meta_description = 'An older description'
        self.product.save()

        context = panel_context(self.product)

        self.assertEqual(context['seo']['title'], 'Typed before v0.47')
        self.assertEqual(context['seo']['description'], 'An older description')

    def test_what_the_merchant_typed_beats_what_autofill_guessed(self):
        """The bug this phase exists to end.

        `autofill_meta_for` writes SeoMeta.title from the product's NAME on
        creation, and the row outranked the native column — so a merchant who
        filled in the product form's meta title watched the storefront go on
        showing the plain product name, with their edit stored and ignored.
        """
        from plugins.installed.seo.services import resolve_meta

        meta = SeoMeta.for_obj(self.product)
        self.assertIsNotNone(meta, 'products are expected to be autofilled on create')
        self.assertTrue(meta.auto_filled)
        self.assertEqual(meta.title, 'Panel Probe')  # the guess: the product name

        self.product.meta_title = 'The title the merchant chose'
        self.product.save()

        self.assertEqual(resolve_meta(obj=self.product).title, 'The title the merchant chose')

    def test_a_panel_edit_outranks_the_native_column_from_then_on(self):
        """Once the merchant uses the panel the row stops being a guess, and
        the deprecated column must not claw the value back."""
        from plugins.installed.seo.services import resolve_meta

        self.product.meta_title = 'The old column'
        self.product.save()
        save_object_seo(self.product, {'seo_title': 'The panel value'})

        self.assertFalse(SeoMeta.for_obj(self.product).auto_filled)
        self.assertEqual(resolve_meta(obj=self.product).title, 'The panel value')

    def test_a_stored_override_outranks_the_native_column(self):
        self.product.meta_title = 'The old column'
        self.product.save()
        save_object_seo(self.product, {'seo_title': 'The panel value'})

        self.assertEqual(panel_context(self.product)['seo']['title'], 'The panel value')

    def test_saving_records_that_the_merchant_wrote_it(self):
        save_object_seo(self.product, {'seo_title': 'Hand written'})
        self.assertEqual(SeoMeta.for_obj(self.product).provenance.get('title'), 'merchant')

    def test_the_native_noindex_flag_is_read_through(self):
        self.product.noindex = True
        self.product.save()
        self.assertTrue(panel_context(self.product)['seo_noindex'])


class PanelContributionTests(TestCase):
    """The card reaches every entity form, and leaves with the app."""

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Card Probe', slug='card-probe', sku='CP-1', price=Decimal('9.00')
        )
        cls.category = Category.objects.create(name='Card Category', slug='card-category')
        cls.collection = Collection.objects.create(name='Card Collection', slug='card-collection')

    def setUp(self):
        self.client.force_login(_staff())

    def _urls(self):
        return {
            'product': reverse(
                'admin_dashboard:product_edit', kwargs={'product_id': self.product.id}
            ),
            'category': reverse(
                'admin_dashboard:category_edit', kwargs={'category_id': self.category.id}
            ),
            'collection': reverse(
                'admin_dashboard:collection_edit', kwargs={'collection_id': self.collection.id}
            ),
        }

    def test_the_panel_renders_on_every_entity_form(self):
        for kind, url in self._urls().items():
            with self.subTest(kind=kind):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    MARKER,
                    response.content.decode(),
                    f'the SEO panel is missing from the {kind} form',
                )

    def test_every_panel_disappears_when_the_seo_app_is_disabled(self):
        app_registry.deactivate('seo')
        self.addCleanup(app_registry.activate, 'seo')
        for kind, url in self._urls().items():
            with self.subTest(kind=kind):
                response = self.client.get(url)
                # The form still works — only the contributed card is gone.
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(
                    MARKER,
                    response.content.decode(),
                    f'the {kind} form kept the SEO panel after seo was disabled',
                )
