"""General → Permalinks panel: saving, validation and SEO safety.

The panel is deliberately on the General page next to store details, so the
first thing these tests pin is that the two forms stay independent: a bad
permalink must not block a store-detail save, and a General save must not wipe
the stored permalink overrides.
"""

from django.test import TestCase

from core.models import StoreSettings
from plugins.installed.admin_dashboard.forms.settings import (
    PERMALINK_DEFAULTS,
    PermalinksForm,
    StoreGeneralForm,
)


class PermalinksFormTests(TestCase):
    def _payload(self, **overrides) -> dict:
        data = {k: '' for k in PERMALINK_DEFAULTS}
        data.update(overrides)
        return data

    def test_defaults_are_prefilled_from_code(self):
        form = PermalinksForm(instance=None)
        self.assertEqual(form.fields['booking'].initial, '/bookings/{slug}/')

    def test_saving_nothing_stores_no_overrides(self):
        form = PermalinksForm(self._payload())
        self.assertTrue(form.is_valid(), form.errors)
        settings = form.save()
        self.assertEqual(settings.permalink_templates, {})

    def test_an_override_is_persisted(self):
        form = PermalinksForm(self._payload(booking='/experiences/{slug}/'))
        self.assertTrue(form.is_valid(), form.errors)
        settings = form.save()
        self.assertEqual(settings.permalink_templates, {'booking': '/experiences/{slug}/'})

    def test_a_default_value_is_not_stored_as_an_override(self):
        """Keeping defaults out of the row means a future default change lands."""
        form = PermalinksForm(self._payload(place='/places/{slug}/'))
        self.assertTrue(form.is_valid(), form.errors)
        settings = form.save()
        self.assertNotIn('place', settings.permalink_templates)

    def test_an_absolute_url_is_rejected_with_a_field_error(self):
        form = PermalinksForm(self._payload(place='https://evil.example.com/{slug}/'))
        self.assertFalse(form.is_valid())
        self.assertIn('place', form.errors)

    def test_a_query_string_is_rejected(self):
        form = PermalinksForm(self._payload(place='/destinations/{slug}/?utm=1'))
        self.assertFalse(form.is_valid())
        self.assertIn('place', form.errors)

    def test_a_missing_placeholder_is_rejected(self):
        form = PermalinksForm(self._payload(place='/destinations/fixed/'))
        self.assertFalse(form.is_valid())
        self.assertIn('place', form.errors)

    def test_an_existing_override_is_prefilled_back_into_the_form(self):
        instance = StoreSettings.objects.create(permalink_templates={'hotel': '/stays/{slug}/'})
        form = PermalinksForm(instance=instance)
        self.assertEqual(form.fields['hotel'].initial, '/stays/{slug}/')
        self.assertEqual(form.fields['place'].initial, '/places/{slug}/')


class GeneralPanelWiringTests(TestCase):
    def setUp(self):
        self.instance = StoreSettings.objects.create(store_name='Test Store')
        self.client.force_login(_staff_user())

    def test_the_general_page_renders_the_permalinks_card(self):
        resp = self.client.get('/dashboard/settings/general/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Permalinks')
        self.assertContains(resp, 'name="booking"')

    def test_the_permalinks_form_posts_to_its_own_form_key(self):
        resp = self.client.post(
            '/dashboard/settings/general/',
            {
                '_form': 'permalinks',
                'booking': '/experiences/{slug}/',
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.permalink_templates, {'booking': '/experiences/{slug}/'})

    def test_an_invalid_permalink_does_not_touch_store_details(self):
        self.client.post(
            '/dashboard/settings/general/',
            {
                '_form': 'permalinks',
                'booking': 'https://example.com/{slug}/',
            },
        )
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.store_name, 'Test Store')
        self.assertEqual(self.instance.permalink_templates, {})

    def test_a_store_detail_save_leaves_permalinks_alone(self):
        self.instance.permalink_templates = {'place': '/destinations/{slug}/'}
        self.instance.save()
        form = StoreGeneralForm(
            {
                'store_name': 'Renamed',
                'store_description': '',
                'primary_currency': 'EUR',
                'country': 'ME',
                'core_language': 'en',
                'timezone': 'UTC',
                'contact_email': '',
                'support_phone': '',
            },
            instance=self.instance,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.permalink_templates, {'place': '/destinations/{slug}/'})


def _staff_user():
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user(
        username='seo-staff', email='seo@example.com', password='x'
    )
    user.is_staff = True
    user.is_superuser = True
    user.save()
    return user
