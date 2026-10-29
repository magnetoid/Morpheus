"""GA4 and GTM in the shopper's browser, on every theme (v0.127.0).

Until v0.127.0 no store ran a Google tag in the browser: three themes called the
GTM tags themselves and montenegro never did (it had a container set and none on
its pages); a store with only a GA4 measurement ID got nothing, because only a
GTM container was ever loaded; a container that did load ran with Consent Mode
denied even after the visitor accepted, because nothing sent the update; and the
cross-domain, server-side GTM and user ID settings had no reader at all.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.template import Context, Template
from django.test import RequestFactory, TestCase

from plugins.installed.tracking.models import TrackingSettings
from plugins.installed.tracking.services.identity import user_id

_HEAD = Template('{% load tracking %}{% tracking_head %}')
_NOSCRIPT = Template('{% load tracking %}{% tracking_noscript %}')


def _gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


def _configure(**fields) -> TrackingSettings:
    s = TrackingSettings.get_solo()
    for key, value in fields.items():
        setattr(s, key, value)
    s.save()
    return s


class _Base(TestCase):
    def setUp(self):
        _gdpr(False)
        self.rf = RequestFactory()

    def render(self, template=_HEAD, path='/', cookies=None, user=None):
        request = self.rf.get(path, HTTP_HOST='testserver')
        request.COOKIES.update(cookies or {})
        if user is not None:
            request.user = user
        return template.render(Context({'request': request}))


class EveryThemeTests(_Base):
    def test_the_container_reaches_the_page_once_through_the_slot(self):
        _configure(gtm_container_id='GTM-ABC1234')
        body = self.client.get('/').content.decode()
        self.assertEqual(body.count('gtm.js?id=GTM-ABC1234'), 1)
        self.assertLess(body.index('"consent","default"'), body.index('gtm.js?id=GTM-ABC1234'))
        self.assertIn('ns.html?id=GTM-ABC1234', body)

    def test_no_theme_calls_the_retired_tags(self):
        root = Path(settings.BASE_DIR) / 'themes' / 'library'
        for base in root.glob('*/templates/storefront/base.html'):
            with self.subTest(theme=base.parts[-4]):
                text = base.read_text()
                for tag in ('gtm_consent_default', 'gtm_head', 'gtm_noscript_body'):
                    self.assertNotIn(tag, text)

    def test_the_retired_tags_render_nothing(self):
        _configure(gtm_container_id='GTM-ABC1234')
        out = Template(
            '{% load tracking %}{% gtm_consent_default %}{% gtm_head %}{% gtm_noscript_body %}'
        ).render(Context({}))
        self.assertEqual(out, '')


class LoaderTests(_Base):
    def test_ga4_alone_loads_gtag_with_its_config(self):
        _configure(measurement_id='G-TEST1234')
        out = self.render()
        self.assertIn('googletagmanager.com/gtag/js?id=G-TEST1234', out)
        self.assertIn('gtag("config","G-TEST1234",{})', out)
        self.assertNotIn('gtm.js', out)

    def test_a_container_wins_over_the_measurement_id(self):
        # GA4 then runs from the container's tags; loading gtag too would count twice.
        _configure(measurement_id='G-TEST1234', gtm_container_id='GTM-ABC1234')
        out = self.render()
        self.assertIn('gtm.js?id=GTM-ABC1234', out)
        self.assertNotIn('gtag/js', out)

    def test_nothing_set_prints_only_the_consent_defaults(self):
        out = self.render()
        self.assertIn('"consent","default"', out)
        self.assertNotIn('googletagmanager', out)

    def test_client_side_off_prints_nothing(self):
        _configure(gtm_container_id='GTM-ABC1234', client_side_enabled=False)
        self.assertEqual(self.render(), '')

    def test_a_malformed_id_is_never_printed(self):
        _configure(gtm_container_id="GTM-1');alert(1);//")
        out = self.render()
        self.assertNotIn('alert', out)
        self.assertNotIn('gtm.js', out)

    def test_a_blocked_path_loads_no_tag(self):
        _configure(gtm_container_id='GTM-ABC1234', block_paths=['/account/'])
        self.assertNotIn('gtm.js', self.render(path='/account/orders/'))
        self.assertNotIn('ns.html', self.render(_NOSCRIPT, path='/account/orders/'))
        self.assertIn('gtm.js', self.render(path='/products/'))


class ConsentTests(_Base):
    def setUp(self):
        super().setUp()
        _gdpr(True)
        _configure(gtm_container_id='GTM-ABC1234')

    @staticmethod
    def _cookie(**choice):
        return {'morpheus_consent': json.dumps({'necessary': True, **choice})}

    def _update(self, out):
        marker = 'gtag("consent","update",'
        return json.loads(out[out.index(marker) + len(marker) : out.index(');', out.index(marker))])

    def test_no_answer_loads_no_tag(self):
        out = self.render()
        self.assertIn('"consent","default"', out)
        self.assertNotIn('gtm.js', out)
        self.assertEqual(self.render(_NOSCRIPT), '')

    def test_analytics_loads_the_tag_with_analytics_granted_only(self):
        out = self.render(cookies=self._cookie(analytics=True))
        self.assertIn('gtm.js?id=GTM-ABC1234', out)
        update = self._update(out)
        self.assertEqual(update['analytics_storage'], 'granted')
        self.assertEqual(update['ad_storage'], 'denied')
        self.assertEqual(update['ad_user_data'], 'denied')

    def test_marketing_grants_the_ad_signals(self):
        update = self._update(self.render(cookies=self._cookie(analytics=True, marketing=True)))
        self.assertEqual(update['ad_storage'], 'granted')
        self.assertEqual(update['ad_personalization'], 'granted')

    def test_a_store_that_does_not_manage_consent_loads_the_tag(self):
        _gdpr(False)
        update = self._update(self.render())
        self.assertEqual(update['analytics_storage'], 'granted')

    def test_the_debug_override_loads_the_tag(self):
        _configure(consent_override=True)
        self.assertIn('gtm.js', self.render())

    def test_a_page_rendered_for_a_choice_is_never_edge_cached(self):
        self.assertIn('public', self.client.get('/products/').get('Cache-Control', ''))
        self.client.cookies['morpheus_consent'] = json.dumps({'analytics': True})
        resp = self.client.get('/products/')
        self.assertNotIn('public', resp.get('Cache-Control', ''))


class IdentityAndRoutingTests(_Base):
    def test_cross_domain_links_this_shop_and_the_listed_domains(self):
        _configure(measurement_id='G-TEST1234', cross_domain='book.example.com, Blog.example.com')
        out = self.render()
        self.assertIn(
            '"linker",{"domains": ["testserver", "book.example.com", "blog.example.com"]}', out
        )

    def test_a_server_container_serves_the_tags(self):
        _configure(gtm_container_id='GTM-ABC1234', sgtm_server_url='https://metrics.shop.example/')
        self.assertIn('https://metrics.shop.example/gtm.js?id=GTM-ABC1234', self.render())
        self.assertIn('https://metrics.shop.example/ns.html?id=GTM-ABC1234', self.render(_NOSCRIPT))
        _configure(gtm_container_id='', measurement_id='G-TEST1234')
        out = self.render()
        self.assertIn('https://metrics.shop.example/gtag/js?id=G-TEST1234', out)
        self.assertIn('"server_container_url": "https://metrics.shop.example"', out)

    def test_a_plain_http_server_container_is_ignored(self):
        _configure(gtm_container_id='GTM-ABC1234', sgtm_server_url='http://metrics.shop.example')
        self.assertIn('https://www.googletagmanager.com/gtm.js', self.render())

    def test_a_signed_in_customer_gets_the_hashed_user_id(self):
        user = get_user_model().objects.create_user(username='u1', email='u1@example.com')
        _configure(measurement_id='G-TEST1234')
        self.assertNotIn('user_id', self.render(user=user))
        _configure(user_id_enabled=True)
        out = self.render(user=user)
        self.assertIn(f'"user_id": "{user_id(user.pk)}"', out)


class EcommercePushTests(_Base):
    def _push(self):
        return Template('{% load tracking %}{% dl_view_item p %}').render(
            Context({'p': {'name': 'Map', 'slug': 'map', 'sku': 'MAP-1', 'price': 4}})
        )

    def test_gtm_gets_a_datalayer_event_after_the_page_is_parsed(self):
        _configure(gtm_container_id='GTM-ABC1234')
        out = self._push()
        self.assertIn('dataLayer.push({ecommerce:null})', out)
        self.assertIn('"event": "view_item"', out)
        self.assertIn('DOMContentLoaded', out)

    def test_ga4_alone_gets_a_gtag_event(self):
        # gtag.js never reads a pushed {event: …} object.
        _configure(measurement_id='G-TEST1234')
        out = self._push()
        self.assertIn('gtag("event","view_item",', out)
        self.assertNotIn('"event": "view_item"', out)

    def test_stored_text_cannot_close_the_script(self):
        _configure(gtm_container_id='GTM-ABC1234')
        out = Template('{% load tracking %}{% dl_view_item p %}').render(
            Context({'p': {'name': '</script><b>x', 'slug': 's', 'sku': 'S', 'price': 1}})
        )
        self.assertEqual(out.count('</script>'), 1)
