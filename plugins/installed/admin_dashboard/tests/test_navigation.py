"""The dashboard's navigation is one taxonomy (docs/plans/dashboard-hubs-2026-10.md).

Before v0.81.0 the sidebar listed 95–100 links: five hardcoded groups plus a
group per contributed `section`, settings pages as sidebar links, and the
same app in two places under different names. Now the sidebar is the
sections, each section's pages are tabs on the page, and settings pages are
cards on their category. These tests hold that shape:

* the sidebar is the sections, in order, and only the ones with something in them;
* every tab and tool answers;
* a page knows where it is — tabs, sub-tabs, a detail route, a settings page;
* the breadcrumb shows below a tab, not on the tab's own page;
* a disabled app's tab leaves with it;
* the storefront never pays for the dashboard's navigation.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import contextlib
import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from plugins.installed.admin_dashboard import navigation
from plugins.registry import app_registry

_SIDEBAR = re.compile(r'<nav id="nav-main".*?</nav>', re.S)
_SETTINGS_SIDEBAR = re.compile(r'<nav id="nav-settings".*?</nav>', re.S)
_TABS = re.compile(r'<nav class="hub-tabs".*?</nav>', re.S)


@contextlib.contextmanager
def disabled(name: str):
    """Runtime-disable an app exactly the way the Apps toggle does."""
    assert app_registry.is_active(name), f'{name} must ship active for this test'
    app_registry.deactivate(name)
    cache.clear()
    try:
        yield
    finally:
        app_registry.activate(name)
        cache.clear()


class _Staff(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='nav-owner',
            email='nav-owner@example.test',
            password='x',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)

    def html(self, url: str) -> str:
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.content.decode()


class SidebarTests(_Staff):
    def test_the_sidebar_is_the_sections_in_order(self):
        sidebar = _SIDEBAR.search(self.html('/dashboard/')).group(0)
        keys = re.findall(r'data-section="([a-z]+)"', sidebar)
        expected = [s.key for s in navigation.SECTIONS if s.key in keys]
        self.assertEqual(keys[:-1], expected, 'sections out of order')
        self.assertEqual(keys[-1], 'settings')
        # Home through Analytics are always there; SEO, Channels, Content and
        # Vendors are there because their apps are on in this install.
        for key in ('home', 'ai', 'orders', 'products', 'customers', 'marketing', 'analytics'):
            self.assertIn(key, keys)
        self.assertLessEqual(len(keys), len(navigation.SECTIONS) + 1)

    def test_the_sidebar_lists_no_page_of_an_app(self):
        # The whole point: an app's pages are tabs, not sidebar links. Every
        # link in the sidebar is a section (whose landing may be an app's
        # first tab, e.g. Channels) or Settings — one per section, no more.
        sidebar = _SIDEBAR.search(self.html('/dashboard/orders/')).group(0)
        links = sidebar.count('class="nav-link')
        self.assertEqual(links, len(re.findall('data-section=', sidebar)))
        self.assertLessEqual(links, len(navigation.SECTIONS) + 1)
        for page_url in ('/dashboard/apps/affiliates/programs/', '/dashboard/reviews/'):
            self.assertNotIn(page_url, sidebar)

    def test_a_section_with_nothing_in_it_is_not_listed(self):
        with disabled('marketplace'):
            sidebar = _SIDEBAR.search(self.html('/dashboard/')).group(0)
            self.assertNotIn('data-section="vendors"', sidebar)
        self.assertIn('data-section="vendors"', _SIDEBAR.search(self.html('/dashboard/')).group(0))

    def test_the_settings_sidebar_is_the_categories(self):
        html = self.html('/dashboard/settings/')
        sidebar = _SETTINGS_SIDEBAR.search(html).group(0)
        self.assertNotIn('style="display:none;"', sidebar.split('>', 1)[0])
        cats = re.findall(r'data-category="([a-z-]*)"', sidebar)
        self.assertEqual(cats[0], '')  # Settings overview
        self.assertEqual(cats[-1], 'apps-catalogue')
        from plugins.installed.admin_dashboard.settings_categories import SETTINGS_CATEGORIES

        known = {c.slug for c in SETTINGS_CATEGORIES}
        self.assertTrue(set(cats[1:-1]) <= known, cats)
        self.assertNotIn('/dashboard/apps/', sidebar.replace('/dashboard/apps/"', ''))


class EveryEntryAnswersTests(_Staff):
    def test_every_tab_and_tool_answers(self):
        user = get_user_model().objects.get(username='nav-owner')
        broken = []
        for entry in [*navigation.tabs(user), *navigation.tools()]:
            status = self.client.get(entry.url).status_code
            if status not in (200, 302):
                broken.append((entry.label, entry.url, status))
        self.assertEqual(broken, [])


class WhereAmITests(_Staff):
    def _nav(self, path):
        from django.test import RequestFactory

        request = RequestFactory().get(path)
        request.user = get_user_model().objects.get(username='nav-owner')
        return navigation.build(request)

    def test_a_tab_page_marks_its_section_and_tab(self):
        nav = self._nav('/dashboard/orders/')
        self.assertEqual((nav['mode'], nav['section']), ('main', 'orders'))
        self.assertTrue(nav['tab_root'])
        active = [t['label'] for t in nav['tabs'] if t['active']]
        self.assertEqual(active, ['All orders'])

    def test_a_group_is_one_tab_with_sub_tabs(self):
        nav = self._nav('/dashboard/apps/affiliates/programs/')
        self.assertEqual(nav['section'], 'marketing')
        labels = [t['label'] for t in nav['tabs']]
        self.assertEqual(labels.count('Affiliates'), 1)
        self.assertNotIn('Programs', labels)  # a sub-tab, not a tab
        self.assertEqual([t['label'] for t in nav['subtabs'] if t['active']], ['Programs'])
        self.assertTrue(next(t for t in nav['tabs'] if t['label'] == 'Affiliates')['active'])

    def test_a_record_below_a_tab_belongs_to_it(self):
        nav = self._nav('/dashboard/marketplace/vendors/3f0c9d2e-0000-4000-8000-000000000001/')
        self.assertEqual(nav['section'], 'vendors')
        self.assertFalse(nav['tab_root'])
        self.assertEqual([t['label'] for t in nav['tabs'] if t['active']], ['Vendors'])

    def test_an_app_mount_deeper_than_a_tab_wins(self):
        # /dashboard/analytics/ is the shell's report; /dashboard/analytics/v2/
        # is the analytics app's own tree.
        nav = self._nav('/dashboard/analytics/v2/funnel/')
        self.assertEqual(nav['section'], 'analytics')
        self.assertEqual([t['label'] for t in nav['tabs'] if t['active']], ['Funnel'])

    def test_a_settings_page_switches_to_settings_mode(self):
        nav = self._nav('/dashboard/shipping/zones/')
        self.assertEqual((nav['mode'], nav['category']), ('settings', 'shipping'))
        self.assertEqual(nav['tabs'], [])

    def test_the_catalogue_and_an_app_settings_form_are_settings(self):
        self.assertEqual(self._nav('/dashboard/apps/')['category'], 'apps-catalogue')
        self.assertEqual(self._nav('/dashboard/settings/seo/')['category'], 'channels')

    def test_home_is_home(self):
        nav = self._nav('/dashboard/')
        self.assertEqual(nav['section'], 'home')
        self.assertEqual(nav['tabs'], [])

    def test_the_page_carries_its_place_for_htmx_swaps(self):
        html = self.html('/dashboard/seo/audit/')
        self.assertIn('data-nav-mode="main"', html)
        self.assertIn('data-nav-section="seo"', html)

    def test_an_app_page_is_found_at_its_router_path_too(self):
        # /dashboard/apps/seo/audit/ serves the same page as /dashboard/seo/audit/.
        nav = self._nav('/dashboard/apps/seo/audit/')
        self.assertEqual(nav['section'], 'seo')
        self.assertEqual([t['label'] for t in nav['tabs'] if t['active']], ['Audit'])


class TabStripTests(_Staff):
    def test_tabs_render_and_the_breadcrumb_waits_below_them(self):
        html = self.html('/dashboard/products/')
        strip = _TABS.search(html).group(0)
        for label in ('All products', 'Categories', 'Collections', 'Tags', 'Reviews'):
            self.assertIn(f'>{label}<', strip)
        # On a tab's own page the strip is the location; no breadcrumb.
        self.assertNotIn('aria-label="Breadcrumb"', html)

    def test_a_detail_page_keeps_its_breadcrumb(self):
        from plugins.installed.marketing.models import Coupon

        coupon = Coupon.objects.create(code='NAV10', name='Nav', discount_type='percentage')
        html = self.html(f'/dashboard/marketing/coupons/{coupon.id}/')
        self.assertIn('hub-tabs', html)  # still inside Marketing
        crumbs = re.search(r'aria-label="Breadcrumb".*?</nav>', html, re.S).group(0)
        self.assertIn('href="/dashboard/marketing/coupons/"', crumbs)

    def test_hidden_pages_have_no_tab_but_a_home(self):
        # The stockout forecast is reached from its card; it still belongs to Products.
        html = self.html('/dashboard/apps/inventory/stockout-forecast/')
        self.assertIn('data-nav-section="products"', html)
        self.assertNotIn('>Stockout forecast</a>', _TABS.search(html).group(0))

    def test_a_disabled_apps_tab_leaves(self):
        self.assertIn('>Reviews<', _TABS.search(self.html('/dashboard/products/')).group(0))
        with disabled('reviews'):
            self.assertNotIn('>Reviews<', _TABS.search(self.html('/dashboard/products/')).group(0))

    def test_linda_tabs_sit_inside_the_chat_layout(self):
        html = self.html('/dashboard/assistant/')
        self.assertIn('<div class="linda-page__tabs">', html)
        self.assertEqual(html.count('class="hub-tabs"'), 1)


class StorefrontPaysNothingTests(TestCase):
    def test_no_dashboard_navigation_on_a_shop_page(self):
        from django.test import RequestFactory

        from plugins.installed.admin_dashboard.context_processors import dashboard_nav

        self.assertEqual(dashboard_nav(RequestFactory().get('/products/')), {})

    def test_the_plugin_context_no_longer_counts_badges(self):
        from django.test import RequestFactory

        from plugins.context_processors import plugin_context

        ctx = plugin_context(RequestFactory().get('/'))
        self.assertNotIn('nav_badges', ctx)
        self.assertNotIn('sidebar_sections', ctx)


class IconMapTests(TestCase):
    """The dashboard draws lucide names through a Remix Icon map in base.html;
    an unmapped name renders a blank circle on a real feature (five tabs did
    before v0.81.0: Stays, Redirects, Attribution, Feedback, NPS)."""

    def test_every_navigation_icon_has_a_glyph(self):
        from pathlib import Path

        from django.conf import settings

        from plugins.installed.admin_dashboard import cards
        from plugins.installed.admin_dashboard.settings_categories import SETTINGS_CATEGORIES

        base = Path(settings.BASE_DIR) / (
            'plugins/installed/admin_dashboard/templates/admin_dashboard/base.html'
        )
        mapped = set(re.findall(r"'([a-z0-9-]+)':'ri-", base.read_text(encoding='utf-8')))
        used = {
            *(p.icon for p in app_registry.dashboard_pages()),
            *(c.icon for c in app_registry.dashboard_cards()),
            *(c.icon for c in cards.CORE_CARDS),
            *(t.icon for t in navigation.CORE_TABS),
            *(t.icon for t in navigation.CORE_TOOLS),
            *(s.icon for s in navigation.SECTIONS),
            *(c.icon for c in SETTINGS_CATEGORIES),
        }
        self.assertEqual(sorted(used - mapped), [])
