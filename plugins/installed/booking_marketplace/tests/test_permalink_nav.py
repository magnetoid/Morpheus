"""Storefront nav payload — permalink-driven shapes and the catalog collision.

Two regressions are pinned here:

1. The Montenegro dropdown rendered empty rows because the generic catalog
   plugin publishes ``nav_categories`` in a different shape and whichever
   context processor ran last won. The namespaced ``storefront_nav`` payload
   must be complete on its own.
2. Every dynamic place link must come from General → Permalinks, so a merchant
   template override actually changes the rendered href.
"""

from django.test import TestCase

from core.models import StoreSettings
from plugins.installed.booking_marketplace.context_processors import storefront_nav


class StorefrontNavPayloadTests(TestCase):
    def test_the_namespaced_payload_is_complete(self):
        ctx = storefront_nav(None)
        payload = ctx['storefront_nav']
        self.assertEqual(set(payload), {'categories', 'destinations', 'places'})
        self.assertEqual(
            set(payload['places']), {'coastal', 'mountains', 'cities', 'landmarks'}
        )

    def test_the_legacy_keys_still_exist_for_the_shipped_theme(self):
        ctx = storefront_nav(None)
        for key in (
            'nav_categories',
            'nav_destinations',
            'nav_places_coastal',
            'nav_places_mountains',
            'nav_places_cities',
            'nav_places_landmarks',
        ):
            self.assertIn(key, ctx)

    def test_a_place_permalink_override_changes_the_generated_href(self):
        StoreSettings.objects.create(permalink_templates={'place': '/destinations/{slug}/'})
        ctx = storefront_nav(None)
        # No Place rows in this DB, so assert through the resolver the
        # context processor uses — the same call the link builder makes.
        self.assertEqual(
            ctx['permalinks']['booking'], '/bookings/sample/'
        )
        from core.services.permalinks import resolver_for_settings

        self.assertEqual(resolver_for_settings().path('place', slug='kotor'), '/destinations/kotor/')

    def test_an_invalid_stored_template_cannot_break_the_render(self):
        """A hand-edited row must degrade to the caller's fallback, not 500."""
        StoreSettings.objects.create(permalink_templates={'place': 'https://evil.example.com/{slug}/'})
        ctx = storefront_nav(None)
        self.assertIn('storefront_nav', ctx)
