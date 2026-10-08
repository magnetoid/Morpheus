"""Disable-safety for the dashboard shell's optional-plugin surfaces (ADR 0013).

A ``try/except`` around a sibling-plugin import guards ABSENCE, not DISABLE: a
disabled plugin is still importable and its tables still exist, so its
dashboard surface used to survive the merchant toggling it off on the Apps
page — failing the disable litmus test in CLAUDE.md. Every such site in the
shell now sits behind ``app_registry.is_active(<name>)``. Two layers here:

* **never-500** — with each optional plugin runtime-disabled, every shell page
  it used to leak into still answers 200/302, and the views that *are* that
  plugin's own surface (coupons, theme builder, video CRUD, draft "new order",
  email-template edit) answer 404 — never 500 — and 200 again once re-enabled;
* **surface-vanishes** — with cheap fixtures, the plugin's rows are on the page
  while it is enabled and gone the moment it is disabled, asserted on unique
  markers (ids/urls), never bare display words.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import contextlib
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.registry import app_registry

# Every optional plugin the shell used to import behind a bare try/except.
OPTIONAL_APPS = (
    'cloudflare',
    'seo',
    'cms',
    'ai_assistant',
    'product_videos',
    'metafields',
    'marketing',
    'draft_orders',
    'ai_content',
    'analytics',
)

# Shell pages that must keep rendering whichever optional plugin is off.
SHELL_PAGES = (
    '/dashboard/',
    '/dashboard/products/',
    '/dashboard/orders/',
    '/dashboard/analytics/',
    '/dashboard/ai-insights/',
    '/dashboard/marketing/',
    '/dashboard/settings/',
    '/dashboard/settings/caching/',
    '/dashboard/settings/ai/',
    '/dashboard/settings/notifications/',
    '/dashboard/settings/email-templates/',
    '/dashboard/palette/search/?q=disable',
)


@contextlib.contextmanager
def disabled(name: str):
    """Runtime-disable ``name`` exactly the way the Apps-page toggle does, and
    always re-enable it — the registry is process-global."""
    assert app_registry.is_active(name), f'{name} must ship active for this test'
    app_registry.deactivate(name)
    cache.clear()
    try:
        yield
    finally:
        app_registry.activate(name)
        cache.clear()


def _login_staff(client, username: str):
    user = get_user_model().objects.create_user(
        username=username, email=f'{username}@example.test', password='pw', is_staff=True
    )
    client.force_login(user)
    return user


def _make_product(slug: str = 'disable-safety-book'):
    from plugins.installed.catalog.models import Product

    return Product.objects.create(
        name='Disable Safety Book',
        slug=slug,
        sku=f'SKU-{slug}',
        status='active',
        price=Money(Decimal('10.00'), 'USD'),
        product_type='simple',
    )


class ShellNeverFiveHundredTests(TestCase):
    """With each optional plugin disabled, the shell still renders."""

    def setUp(self):
        _login_staff(self.client, 'disable-shell')
        self.product = _make_product()

    def test_shell_pages_render_with_each_optional_app_disabled(self):
        pages = SHELL_PAGES + (f'/dashboard/products/{self.product.id}/',)
        for name in OPTIONAL_APPS:
            with disabled(name):
                for url in pages:
                    with self.subTest(app=name, url=url):
                        r = self.client.get(url)
                        self.assertIn(r.status_code, (200, 302), f'{url} with {name} off')

    def test_owned_pages_are_404_not_500_under_any_disable(self):
        # The plugin-owned views must never 500 for a *different* plugin's
        # disable either (they are 404 only for their own owner — below).
        from plugins.installed.cms.models import Page

        page = Page.objects.create(slug='ds-owned', title='DS owned')
        # (email_template_edit is asserted 404-when-cms-off in CmsSurfaceTests
        # only: its enabled path 500s on a pre-existing TemplateSyntaxError in
        # email_template_edit.html — literal `{{ "{{ … }}" }}` — unrelated here.)
        owned = {
            '/dashboard/marketing/coupons/': 'marketing',
            '/dashboard/marketing/coupons/new/': 'marketing',
            f'/dashboard/pages/{page.id}/builder/': 'cms',
            '/dashboard/orders/new/': 'draft_orders',
            f'/dashboard/products/{self.product.id}/videos/new/': 'product_videos',
        }
        for name in OPTIONAL_APPS:
            with disabled(name):
                for url, owner in owned.items():
                    with self.subTest(app=name, url=url):
                        r = self.client.get(url)
                        if owner == name:
                            self.assertEqual(r.status_code, 404, f'{url} with {name} off')
                        else:
                            self.assertIn(r.status_code, (200, 302), f'{url} with {name} off')
        # And 200 (or the view's normal redirect) with everything enabled.
        for url in owned:
            with self.subTest(url=url, state='enabled'):
                self.assertIn(self.client.get(url).status_code, (200, 302))

    def test_ai_probe_is_json_503_when_ai_assistant_disabled(self):
        # A JSON endpoint keeps the data-ajax contract (JSON on failure too).
        url = '/dashboard/settings/ai/probe/'
        with disabled('ai_assistant'):
            r = self.client.post(url, {'provider': 'openai'})
            self.assertEqual(r.status_code, 503)
            self.assertFalse(json.loads(r.content)['ok'])
        r = self.client.post(url, {'provider': 'openai'})  # no key stored → fails soft
        self.assertEqual(r.status_code, 200)
        self.assertIn('ok', json.loads(r.content))


class MarketingSurfaceTests(TestCase):
    """(a) The coupon pages are the marketing plugin's surface: 404 when it is
    disabled, back when it is enabled — the coupon row included. The
    Marketing overview above them is the shell's and stays up, the coupons
    card leaving with the app."""

    def setUp(self):
        from plugins.installed.marketing.models import Coupon

        _login_staff(self.client, 'disable-marketing')
        self.coupon = Coupon.objects.create(
            code='DSAFETY10',
            name='Disable safety',
            discount_type='percentage',
            discount_value=Decimal('10'),
        )

    def test_coupon_pages_404_when_disabled_200_when_enabled(self):
        edit = f'/dashboard/marketing/coupons/{self.coupon.id}/'
        delete = f'/dashboard/marketing/coupons/{self.coupon.id}/delete/'
        with disabled('marketing'):
            for url in ('/dashboard/marketing/coupons/', '/dashboard/marketing/coupons/new/', edit):
                self.assertEqual(self.client.get(url).status_code, 404, url)
            self.assertEqual(self.client.post(delete).status_code, 404)
            overview = self.client.get('/dashboard/marketing/')
            self.assertEqual(overview.status_code, 200)
            self.assertNotContains(overview, 'data-card="marketing:Coupons"')
        r = self.client.get('/dashboard/marketing/coupons/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, edit)  # the coupon's own edit URL — unique marker
        self.assertContains(
            self.client.get('/dashboard/marketing/'), 'data-card="marketing:Coupons"'
        )
        self.assertEqual(self.client.get(edit).status_code, 200)
        self.assertEqual(self.client.get('/dashboard/marketing/coupons/new/').status_code, 200)

    def test_delete_does_not_operate_while_disabled(self):
        from plugins.installed.marketing.models import Coupon

        delete = f'/dashboard/marketing/coupons/{self.coupon.id}/delete/'
        with disabled('marketing'):
            self.assertEqual(self.client.post(delete).status_code, 404)
            self.assertTrue(Coupon.objects.filter(pk=self.coupon.pk).exists())
        self.assertEqual(self.client.post(delete).status_code, 302)
        self.assertFalse(Coupon.objects.filter(pk=self.coupon.pk).exists())


class ProductVideoSurfaceTests(TestCase):
    """(b) The product editor's video card + the video CRUD endpoints."""

    def setUp(self):
        from plugins.installed.product_videos.models import ProductVideo

        _login_staff(self.client, 'disable-videos')
        self.product = _make_product('disable-safety-video')
        self.video = ProductVideo.objects.create(
            product=self.product,
            title='DS trailer',
            url='https://www.youtube.com/watch?v=dsafety',
        )
        self.edit_page = f'/dashboard/products/{self.product.id}/'
        base = f'/dashboard/products/{self.product.id}/videos/'
        self.add = f'{base}new/'
        self.edit = f'{base}{self.video.id}/edit/'
        self.delete = f'{base}{self.video.id}/delete/'

    def test_video_vanishes_from_product_editor_when_disabled(self):
        marker = str(self.video.id)  # rendered in the tile + delete-form URLs
        r = self.client.get(self.edit_page)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, marker)
        with disabled('product_videos'):
            r = self.client.get(self.edit_page)
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, marker)
        self.assertContains(self.client.get(self.edit_page), marker)

    def test_video_crud_is_404_when_disabled_and_operates_when_enabled(self):
        from plugins.installed.product_videos.models import ProductVideo

        with disabled('product_videos'):
            self.assertEqual(self.client.get(self.add).status_code, 404)
            self.assertEqual(
                self.client.post(
                    self.add, {'title': 'x', 'url': 'https://v.example/x.mp4'}
                ).status_code,
                404,
            )
            self.assertEqual(self.client.post(self.edit, {'title': 'renamed'}).status_code, 404)
            self.assertEqual(self.client.post(self.delete).status_code, 404)
        self.video.refresh_from_db()
        self.assertEqual(self.video.title, 'DS trailer')  # nothing operated
        self.assertEqual(ProductVideo.objects.filter(product=self.product).count(), 1)
        # Enabled: the JSON edit answers 200, add/delete redirect back to the editor.
        self.assertEqual(self.client.get(self.add).status_code, 302)
        r = self.client.post(self.edit, {'title': 'renamed'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.content)['title'], 'renamed')
        self.assertEqual(self.client.post(self.delete).status_code, 302)
        self.assertFalse(ProductVideo.objects.filter(pk=self.video.pk).exists())


class CachingCloudflareSurfaceTests(TestCase):
    """(c) The Caching settings page: the cloudflare zone rows/controls vanish
    when the plugin is disabled, and the page still renders."""

    def setUp(self):
        from plugins.installed.cloudflare.models import CloudflareAccount, CloudflareZone

        _login_staff(self.client, 'disable-cf')
        self.url = '/dashboard/settings/caching/'
        acct = CloudflareAccount.objects.create(label='acme', api_token='tok')
        self.zone = CloudflareZone.objects.create(
            account=acct, zone_id='zone-ds', domain='ds.example'
        )
        # The zone's own dashboard URL — a marker only the zone rows render.
        self.marker = f'/dashboard/cloudflare/zones/{self.zone.id}/'

    def _get(self):
        # No live CF API read in tests (the per-zone cache-controls block).
        with patch('plugins.installed.cloudflare.services.zone_settings_map', return_value={}):
            return self.client.get(self.url)

    def test_zone_rows_vanish_when_cloudflare_disabled(self):
        r = self._get()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.marker)
        self.assertContains(r, 'name="action" value="cf_purge_all"')
        with disabled('cloudflare'):
            r = self._get()
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, self.marker)
            self.assertNotContains(r, 'value="cf_purge_all"')
        self.assertContains(self._get(), self.marker)

    def test_cf_actions_do_not_operate_when_disabled(self):
        with (
            patch('plugins.installed.cloudflare.services.purge_everything') as purge_fn,
            disabled('cloudflare'),
        ):
            r = self.client.post(self.url, {'action': 'cf_purge_all', 'zone_id': str(self.zone.id)})
        self.assertEqual(r.status_code, 302)  # the page still answers
        purge_fn.assert_not_called()


class CmsSurfaceTests(TestCase):
    """(d) Theme builder + email-template edit are cms surfaces (404 when off);
    the palette stops offering cms pages; the email-templates list still renders."""

    def setUp(self):
        from plugins.installed.cms.models import Page, PageSection

        _login_staff(self.client, 'disable-cms')
        self.page = Page.objects.create(slug='ds-cms-page', title='DisableSafetyPage')
        self.row = PageSection.objects.create(page=self.page, section_id='hero', sort_order=0)
        self.builder = f'/dashboard/pages/{self.page.id}/builder/'

    def test_theme_builder_404_when_disabled_200_when_enabled(self):
        from plugins.installed.cms.models import PageSection

        add = f'{self.builder}add/'
        reorder = f'{self.builder}reorder/'
        update = f'{self.builder}{self.row.id}/update/'
        delete = f'{self.builder}{self.row.id}/delete/'
        with disabled('cms'):
            self.assertEqual(self.client.get(self.builder).status_code, 404)
            self.assertEqual(self.client.post(add, {'section_id': 'hero'}).status_code, 404)
            self.assertEqual(
                self.client.post(reorder, {'ids[]': [str(self.row.id)]}).status_code, 404
            )
            self.assertEqual(self.client.post(update, {'is_visible': '0'}).status_code, 404)
            self.assertEqual(self.client.post(delete).status_code, 404)
        self.row.refresh_from_db()
        self.assertTrue(self.row.is_visible)  # nothing operated while off
        self.assertEqual(self.client.get(self.builder).status_code, 200)
        r = self.client.post(update, {'is_visible': '0'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.post(delete).status_code, 200)
        self.assertFalse(PageSection.objects.filter(pk=self.row.pk).exists())

    def test_email_template_edit_404_when_disabled_list_still_renders(self):
        edit = '/dashboard/settings/email-templates/order_placed/'
        # Enabled path: this page 500'd from 2026-06-13 to v0.45.0 with a
        # TemplateSyntaxError — its placeholder help wrote literal `{{ "{{ … }}" }}`,
        # which the lexer cuts at the first `}}`. Now `{% verbatim %}`; keep the
        # 200 so the help text can never silently take the editor down again.
        self.assertEqual(self.client.get(edit).status_code, 200)
        with disabled('cms'):
            self.assertEqual(
                self.client.get('/dashboard/settings/email-templates/').status_code, 200
            )
            self.assertEqual(self.client.get(edit).status_code, 404)

    def test_palette_stops_offering_cms_pages_when_disabled(self):
        url = '/dashboard/palette/search/?q=DisableSafetyPage'

        def page_hits():
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            return [h for h in json.loads(r.content)['hits'] if h['kind'] == 'page']

        self.assertTrue(page_hits())
        with disabled('cms'):
            self.assertEqual(page_hits(), [])
        self.assertTrue(page_hits())


class DraftOrdersSurfaceTests(TestCase):
    """The Orders page loses its Drafts button and /orders/new/ 404s when
    draft_orders is disabled."""

    def setUp(self):
        _login_staff(self.client, 'disable-drafts')

    def test_drafts_button_and_new_order_page(self):
        r = self.client.get('/dashboard/orders/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'href="/dashboard/draft-orders/" class="btn"')
        self.assertEqual(self.client.get('/dashboard/orders/new/').status_code, 200)
        with disabled('draft_orders'):
            r = self.client.get('/dashboard/orders/')
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, 'href="/dashboard/draft-orders/" class="btn"')
            self.assertEqual(self.client.get('/dashboard/orders/new/').status_code, 404)
