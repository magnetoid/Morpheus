"""Permalink template validation — the URL contract behind General → Permalinks.

These strings feed navigation, canonical tags, the sitemap and hreflang, so the
guard rails matter more than the feature: a template that produces a query
string, a fragment, an absolute URL or a path-traversal segment would silently
poison every one of those surfaces.
"""

from django.test import TestCase

from core.services.permalinks import (
    DEFAULT_TEMPLATES,
    PermalinkError,
    PermalinkResolver,
    validate_template,
)


class ValidateTemplateTests(TestCase):
    def test_the_shipped_defaults_are_all_valid(self):
        for kind, template in DEFAULT_TEMPLATES.items():
            validate_template(kind, template)  # must not raise

    def test_a_clean_local_path_is_accepted(self):
        validate_template('booking', '/experiences/{slug}/')
        validate_template('place', '/destinations/{slug}/')

    def test_an_absolute_url_is_refused(self):
        """An absolute URL would break hreflang and the sitemap host contract."""
        with self.assertRaises(PermalinkError):
            validate_template('booking', 'https://example.com/{slug}/')

    def test_a_query_string_is_refused(self):
        with self.assertRaises(PermalinkError):
            validate_template('booking', '/bookings/{slug}/?ref=1')

    def test_a_fragment_is_refused(self):
        with self.assertRaises(PermalinkError):
            validate_template('booking', '/bookings/{slug}/#top')

    def test_a_missing_slug_placeholder_is_refused(self):
        with self.assertRaises(PermalinkError):
            validate_template('booking', '/bookings/fixed/')

    def test_two_slug_placeholders_are_refused(self):
        with self.assertRaises(PermalinkError):
            validate_template('booking', '/bookings/{slug}/{slug}/')

    def test_another_placeholder_is_refused(self):
        with self.assertRaises(PermalinkError):
            validate_template('booking', '/bookings/{id}/')

    def test_a_path_without_trailing_slash_is_refused(self):
        with self.assertRaises(PermalinkError):
            validate_template('booking', '/bookings/{slug}')

    def test_an_unknown_type_is_refused(self):
        with self.assertRaises(PermalinkError):
            validate_template('not_a_type', '/x/{slug}/')


class ResolverTests(TestCase):
    def test_a_default_template_produces_the_shipped_path(self):
        resolver = PermalinkResolver(DEFAULT_TEMPLATES)
        self.assertEqual(resolver.path('place', slug='kotor'), '/places/kotor/')

    def test_a_merchant_override_wins(self):
        resolver = PermalinkResolver({**DEFAULT_TEMPLATES, 'place': '/destinations/{slug}/'})
        self.assertEqual(resolver.path('place', slug='kotor'), '/destinations/kotor/')

    def test_an_empty_slug_is_refused(self):
        resolver = PermalinkResolver(DEFAULT_TEMPLATES)
        with self.assertRaises(PermalinkError):
            resolver.path('place', slug='')

    def test_a_slug_never_escapes_its_segment(self):
        resolver = PermalinkResolver(DEFAULT_TEMPLATES)
        self.assertEqual(resolver.path('place', slug='../admin'), '/places/..%2Fadmin/')

    def test_an_unknown_type_is_refused(self):
        resolver = PermalinkResolver(DEFAULT_TEMPLATES)
        with self.assertRaises(PermalinkError):
            resolver.path('nope', slug='x')

    def test_settings_without_the_override_key_falls_back_to_defaults(self):
        resolver = PermalinkResolver.from_settings(object())
        self.assertEqual(resolver.path('journal', slug='kotor'), '/journal/kotor/')
