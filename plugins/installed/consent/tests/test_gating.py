"""The consent decision gates the tags, and Global Privacy Control counts.

Until v0.91.0 the banner recorded a decision that nothing read: every ad
pixel and the analytics beacon loaded on every page whatever the visitor
chose. Now the consent app contributes a ``consent`` context on every request
(``managed`` = the store runs consent at all, then the per-category answer),
every marketing block renders only when ``consent.marketing`` allows it and
the analytics beacon only on ``consent.analytics``. A store that switched
GDPR features off, or disabled the app, is unmanaged: its tags fire as before.
A browser sending ``Sec-GPC: 1`` with no decision on file is treated as having
refused everything non-essential (the banner stays out of the way; the
preferences page explains and still allows opting in).
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.cache import cache
from django.template import Context
from django.test import Client, RequestFactory, TestCase

from plugins.installed.consent.services import COOKIE_NAME

MARKETING_APPS = {
    'google_shopping',
    'meta_commerce',
    'microsoft_commerce',
    'pinterest_commerce',
    'reddit_ads',
    'snapchat_commerce',
    'tiktok_commerce',
}


def _cookie(**flags) -> str:
    return json.dumps({'necessary': True, **flags})


def _set_gdpr(on: bool) -> None:
    """Settings → General → GDPR features (the banner and the gate exist only
    while it is on). Same shape as storefront's test_gdpr_toggle."""
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


def _enable_meta_pixel():
    from plugins.registry import app_registry

    p = app_registry.get('meta_commerce')
    p.set_config('pixel_enabled', True)
    p.set_config('pixel_id', '123456789012345')
    p.invalidate_config_cache()
    return p


class ContextProcessorTests(TestCase):
    def setUp(self):
        cache.clear()

    def _consent(self, **extra):
        from plugins.installed.consent.context_processors import consent_context

        request = RequestFactory().get('/', **extra)
        return consent_context(request)['consent']

    def test_no_decision_is_necessary_only_and_managed(self):
        c = self._consent()
        self.assertTrue(c['managed'])
        self.assertFalse(c['decided'])
        self.assertFalse(c['marketing'])
        self.assertFalse(c['analytics'])
        self.assertFalse(c['gpc'])

    def test_a_decision_is_read_from_the_cookie(self):
        c = self._consent(HTTP_COOKIE=f'{COOKIE_NAME}={_cookie(marketing=True, analytics=False)}')
        self.assertTrue(c['decided'])
        self.assertTrue(c['marketing'])
        self.assertFalse(c['analytics'])

    def test_global_privacy_control_counts_as_a_refusal(self):
        from plugins.installed.consent.services import has_decided

        request = RequestFactory().get('/', HTTP_SEC_GPC='1')
        self.assertTrue(has_decided(request))
        c = self._consent(HTTP_SEC_GPC='1')
        self.assertTrue(c['gpc'])
        self.assertTrue(c['decided'])
        self.assertFalse(c['marketing'])
        self.assertFalse(c['analytics'])

    def test_an_explicit_choice_beats_the_gpc_signal(self):
        c = self._consent(HTTP_SEC_GPC='1', HTTP_COOKIE=f'{COOKIE_NAME}={_cookie(marketing=True)}')
        self.assertTrue(c['gpc'])
        self.assertTrue(c['marketing'])

    def test_a_store_with_gdpr_features_off_is_unmanaged(self):
        _set_gdpr(False)
        self.addCleanup(_set_gdpr, True)
        c = self._consent()
        self.assertFalse(c['managed'])


class BannerTests(TestCase):
    def test_gpc_hides_the_banner(self):
        from plugins.installed.consent.templatetags.consent import consent_show

        cache.clear()
        request = RequestFactory().get('/', HTTP_SEC_GPC='1')
        self.assertFalse(consent_show(Context({'request': request})))
        self.assertTrue(consent_show(Context({'request': RequestFactory().get('/')})))

    def test_the_preferences_page_explains_gpc(self):
        r = Client().get('/consent/preferences/', HTTP_SEC_GPC='1')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Global Privacy Control')
        r = Client().get('/consent/preferences/')
        self.assertNotContains(r, 'Global Privacy Control')


class TagGatingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.plugin = _enable_meta_pixel()
        self.addCleanup(self.plugin.set_config, 'pixel_enabled', False)
        self.addCleanup(self.plugin.invalidate_config_cache)

    def test_pixels_wait_for_marketing_consent(self):
        body = Client().get('/').content.decode()
        self.assertNotIn('fbq(', body)
        self.assertNotIn('/api/analytics/track/', body)

        c = Client()
        c.cookies[COOKIE_NAME] = _cookie(marketing=True, analytics=True)
        body = c.get('/').content.decode()
        self.assertIn('fbq(', body)
        self.assertIn('/api/analytics/track/', body)

    def test_analytics_consent_alone_loads_only_the_beacon(self):
        c = Client()
        c.cookies[COOKIE_NAME] = _cookie(marketing=False, analytics=True)
        body = c.get('/').content.decode()
        self.assertIn('/api/analytics/track/', body)
        self.assertNotIn('fbq(', body)

    def test_an_unmanaged_store_keeps_its_tags(self):
        _set_gdpr(False)
        self.addCleanup(_set_gdpr, True)
        body = Client().get('/').content.decode()
        self.assertIn('fbq(', body)
        self.assertIn('/api/analytics/track/', body)

    def test_a_disabled_consent_app_keeps_the_tags(self):
        from plugins.registry import app_registry

        app_registry.deactivate('consent')
        self.addCleanup(app_registry.activate, 'consent')
        body = Client().get('/').content.decode()
        self.assertIn('fbq(', body)


class EveryMarketingBlockIsGatedTests(TestCase):
    """A static guard: a new pixel block that forgets the gate fails here."""

    def test_every_marketing_block_reads_consent(self):
        from django.template.loader import get_template

        from plugins.registry import app_registry

        seen = set()
        for block in app_registry.storefront_blocks_for('global_below_body'):
            if block.plugin in MARKETING_APPS:
                seen.add(block.plugin)
                source = Path(get_template(block.template).origin.name).read_text()
                self.assertIn('consent.marketing', source, block.template)
            if block.plugin == 'analytics':
                source = Path(get_template(block.template).origin.name).read_text()
                self.assertIn('consent.analytics', source, block.template)
        self.assertEqual(seen, MARKETING_APPS)
