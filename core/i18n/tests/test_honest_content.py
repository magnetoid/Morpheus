"""Which content is translatable, and showing a reviewed translation safely (v0.160.0)."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings
from djmoney.money import Money

from core.i18n import services as i18n

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}


def _product(**extra):
    from plugins.installed.catalog.models import Product

    fields = {
        'name': 'Sea Kayak',
        'slug': 'sea-kayak',
        'sku': 'SK-1',
        'status': 'active',
        'price': Money(Decimal('9.00'), 'EUR'),
        'description': '<p>A calm paddle.</p>',
        **extra,
    }
    return Product.objects.create(**fields)


@override_settings(**BILINGUAL)
class OverlayTests(TestCase):
    def test_an_overlaid_instance_saves_its_own_language(self):
        product = _product()
        i18n.set_translation(product, 'name', 'sr', 'Morski kajak')
        i18n.set_translation(product, 'description', 'sr', '<p>Mirno veslanje.</p>')
        i18n.overlay_translation(product, 'sr')
        self.assertEqual(product.name, 'Morski kajak')
        self.assertEqual(product.__dict__['_morph_translated'], 'sr')
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.name, 'Sea Kayak')
        self.assertEqual(product.description, '<p>A calm paddle.</p>')

    def test_a_partial_translation_is_not_shown(self):
        product = _product()
        i18n.set_translation(product, 'name', 'sr', 'Morski kajak')
        i18n.overlay_translation(product, 'sr')
        self.assertEqual(product.name, 'Sea Kayak')
        self.assertNotIn('_morph_translated', product.__dict__)

    def test_a_draft_is_not_shown(self):
        product = _product()
        i18n.set_translation(product, 'name', 'sr', 'Morski kajak', reviewed=False)
        i18n.set_translation(product, 'description', 'sr', '<p>Mirno.</p>', reviewed=False)
        i18n.overlay_translation(product, 'sr')
        self.assertEqual(product.name, 'Sea Kayak')

    def test_nothing_happens_in_the_default_language(self):
        product = _product()
        i18n.set_translation(product, 'name', 'en', 'Other')
        i18n.overlay_translation(product, 'en')
        self.assertEqual(product.name, 'Sea Kayak')


@override_settings(**BILINGUAL)
class ContentLanguagesTests(TestCase):
    def test_the_default_language_always_counts(self):
        self.assertEqual(i18n.content_languages(_product()), {'en'})

    def test_every_filled_field_must_be_reviewed(self):
        product = _product()
        i18n.set_translation(product, 'name', 'sr', 'Morski kajak')
        self.assertEqual(i18n.content_languages(product), {'en'})
        i18n.set_translation(product, 'description', 'sr', '<p>Mirno.</p>', reviewed=False)
        self.assertEqual(i18n.content_languages(product), {'en'})
        i18n.set_translation(product, 'description', 'sr', '<p>Mirno.</p>')
        self.assertEqual(i18n.content_languages(product), {'en', 'sr'})

    def test_an_unregistered_model_is_not_judged(self):
        from core.models import StoreSettings

        self.assertIsNone(i18n.content_languages(StoreSettings.objects.create(store_name='S')))

    def test_a_draft_never_replaces_a_reviewed_translation(self):
        product = _product()
        i18n.set_translation(product, 'name', 'sr', 'Morski kajak')
        i18n.set_translation(product, 'name', 'sr', 'Drugo', reviewed=False)
        self.assertEqual(i18n.get_translation(product, 'name', 'sr'), 'Morski kajak')

    def test_approval_keeps_the_ai_provenance(self):
        from core.i18n.models import Translation

        product = _product()
        i18n.set_translation(
            product, 'name', 'sr', 'Kajak', machine_translated=True, reviewed=False
        )
        self.assertEqual(i18n.approve_drafts(product, 'sr'), 1)
        row = Translation.objects.get(field='name', language_code='sr')
        self.assertTrue(row.reviewed)
        self.assertTrue(row.is_machine_translated)


class CleanWriteTests(TestCase):
    def test_html_is_sanitised_and_text_is_plain_and_clipped(self):
        product = _product()
        row = i18n.set_translation(
            product, 'description', 'sr', '<p>Dobro</p><script>alert(1)</script>'
        )
        self.assertNotIn('<script', row.value)
        self.assertIn('<p>Dobro</p>', row.value)
        row = i18n.set_translation(product, 'name', 'sr', '<b>Ime</b> ' + 'x' * 400)
        self.assertFalse(row.value.startswith('<b>'))
        self.assertLessEqual(len(row.value), 300)

    def test_an_unregistered_field_is_stored_as_given(self):
        from core.models import StoreSettings

        store = StoreSettings.objects.create(store_name='S')
        row = i18n.set_translation(store, 'store_name', 'sr', '<b>Radnja</b>')
        self.assertEqual(row.value, '<b>Radnja</b>')


class RegistryTests(TestCase):
    def test_the_owners_register_their_content(self):
        keys = {spec['key'] for spec in i18n.translatable_specs()}
        self.assertIn('catalog.product', keys)
        self.assertIn('cms.page', keys)

    def test_a_disabled_owner_takes_its_content_with_it(self):
        from plugins.registry import app_registry

        self.addCleanup(app_registry.activate, 'cms')
        app_registry.deactivate('cms')
        self.assertNotIn('cms.page', {spec['key'] for spec in i18n.translatable_specs()})

    @override_settings(**BILINGUAL)
    def test_a_page_built_from_sections_is_left_out(self):
        from plugins.installed.cms.models import Page, PageSection

        page = Page.objects.create(slug='landing', title='Landing', state='published')
        PageSection.objects.create(page=page, section_id='hero', is_visible=True)
        self.assertIsNone(i18n.content_languages(page))
        plain = Page.objects.create(slug='about', title='About', state='published')
        self.assertEqual(i18n.content_languages(plain), {'en'})
