"""Regression: the Montenegro header must not 500 when its nav data is absent.

This is the production failure being pinned. The theme reads several megamenu
keys, and Django's template engine raises ``VariableDoesNotExist`` for a missing
nested lookup — a ``|default:`` filter does NOT rescue it. So if the booking
plugin is inactive (or its context processor is not registered, which is how
this actually broke) the storefront returned a hard 500 instead of rendering
without a menu.
"""

from django.template.loader import get_template
from django.test import RequestFactory, TestCase


class MontenegroNavFallbackTests(TestCase):
    def _render(self, extra: dict):
        request = RequestFactory().get('/')
        request.session = {}
        request.user = None
        return get_template('storefront/base.html').render(extra, request)

    def test_the_header_renders_with_no_nav_context_at_all(self):
        """The exact production shape: none of the nav keys exist."""
        html = self._render({})
        self.assertIn('</html>', html)

    def test_the_header_renders_with_the_legacy_keys_only(self):
        """A store whose nav comes from the legacy keys still gets a menu."""
        html = self._render(
            {
                'nav_categories': [{'name': 'Hiking', 'slug': 'hiking'}],
                'nav_destinations': [{'name': 'Kotor', 'slug': 'kotor'}],
                'nav_places_coastal': [{'name': 'Budva', 'slug': 'budva'}],
                'nav_places_mountains': [],
                'nav_places_cities': [],
                'nav_places_landmarks': [],
            }
        )
        self.assertIn('Hiking', html)
        self.assertIn('/places/kotor/', html)

    def test_the_header_renders_with_the_namespaced_payload_only(self):
        """The booking plugin's own shape, without the legacy aliases."""
        html = self._render(
            {
                'storefront_nav': {
                    'categories': [{'label': 'Sailing', 'slug': 'sailing'}],
                    'destinations': [{'name': 'Perast', 'slug': 'perast', 'href': '/places/perast/'}],
                    'places': {
                        'coastal': [{'name': 'Tivat', 'slug': 'tivat', 'href': '/places/tivat/'}],
                        'mountains': [],
                        'cities': [],
                        'landmarks': [],
                    },
                },
            }
        )
        self.assertIn('Sailing', html)
        self.assertIn('/places/tivat/', html)


class NavContextProcessorRegistrationTests(TestCase):
    def test_the_booking_plugin_registers_its_storefront_nav_processor(self):
        """Written-but-unregistered was the actual bug: the module existed and
        every theme assumed its keys, but nothing ever contributed it."""
        from plugins.registry import app_registry

        names = {func.__name__ for func, _owner in app_registry.context_processors()}
        self.assertIn('storefront_nav', names)
