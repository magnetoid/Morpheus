"""Product placeholder image — Settings → General field + storefront fallback."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

from core.context_processors import store_settings
from core.models import StoreSettings


class PlaceholderImageContextTests(TestCase):
    def test_url_empty_when_unset(self):
        ctx = store_settings(RequestFactory().get('/'))
        self.assertEqual(ctx['PRODUCT_PLACEHOLDER_IMAGE'], '')

    def test_url_exposed_when_set(self):
        StoreSettings.objects.create(product_placeholder_image='store/ph.png')
        ctx = store_settings(RequestFactory().get('/'))
        self.assertTrue(ctx['PRODUCT_PLACEHOLDER_IMAGE'].endswith('/store/ph.png'))


class ProductCardFallbackTests(TestCase):
    def _render(self, placeholder: str) -> str:
        # No request → context processors don't run (the card's only tag,
        # caching_img_loading_attr, takes no request), so we test the template
        # branch in isolation.
        product = {'name': 'No Cover Book', 'slug': 'no-cover', 'id': 'abc-123'}
        return render_to_string(
            'storefront/_product_card.html',
            {'product': product, 'PRODUCT_PLACEHOLDER_IMAGE': placeholder},
        )

    def test_uses_placeholder_image_when_set_and_no_product_image(self):
        html = self._render('/media/store/ph.png')
        self.assertIn('/media/store/ph.png', html)
        self.assertNotIn('class="placeholder"', html)  # text fallback not used

    def test_text_placeholder_when_no_setting(self):
        html = self._render('')
        self.assertIn('class="placeholder"', html)
        self.assertNotIn('/media/store/ph.png', html)


class StoreGeneralFormTests(TestCase):
    def test_save_does_not_clobber_image_when_no_upload(self):
        from plugins.installed.admin_dashboard.forms.settings import StoreGeneralForm

        existing = StoreSettings.objects.create(product_placeholder_image='store/ph.png')
        form = StoreGeneralForm(
            data={'store_name': 'Shop', 'primary_currency': 'USD', 'country': 'US'},
            instance=existing,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        # No new file uploaded → the stored placeholder image is preserved.
        self.assertEqual(saved.product_placeholder_image.name, 'store/ph.png')
