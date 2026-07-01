"""Phase 1b storefront language routing (ADR 0022): core language unprefixed,
other languages /<code>/-prefixed; dashboard/api stay UNprefixed.

Verified via URL resolution (no browser): proves the storefront is reachable at
both `/` and `/fr/`, and that chrome surfaces are NOT language-routed.
"""

from django.test import SimpleTestCase
from django.urls import Resolver404, resolve, reverse
from django.utils import translation


class StorefrontLanguageRoutingTests(SimpleTestCase):
    """LocaleMiddleware activates the language from the URL prefix before
    resolution; these tests mirror that with translation.override()."""

    def test_core_language_storefront_unprefixed(self):
        self.assertEqual(resolve('/').view_name, 'storefront:home')

    def test_prefixed_language_resolves_storefront(self):
        with translation.override('fr'):
            self.assertEqual(resolve('/fr/').view_name, 'storefront:home')
            self.assertEqual(resolve('/fr/cart/').view_name, 'storefront:cart')

    def test_reverse_prefixes_non_core_language_only(self):
        # Internal links auto-prefix per active language (so /fr/ persists while
        # browsing); the core language stays unprefixed.
        with translation.override('fr'):
            self.assertEqual(reverse('storefront:home'), '/fr/')
        with translation.override('en'):
            self.assertEqual(reverse('storefront:home'), '/')

    def test_dashboard_not_language_prefixed(self):
        # /dashboard/ resolves (chrome, unprefixed)…
        self.assertTrue(resolve('/dashboard/'))
        # …but a language-prefixed dashboard path must NOT resolve — chrome is
        # outside i18n_patterns.
        with translation.override('fr'), self.assertRaises(Resolver404):
            resolve('/fr/dashboard/')

    def test_healthz_unaffected(self):
        self.assertEqual(resolve('/healthz').func.__name__, '_healthz')

    def test_set_language_view_mounted(self):
        self.assertTrue(resolve('/i18n/setlang/'))
