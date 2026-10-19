"""Staff edit a vendor from the dashboard, and Linda can too (owner, 2026-10-19).

The Vendors section listed vendors and showed their sales, but nothing could
change a vendor's name, description, logo, status or web address. The form and
Linda's `vendors.update` save through the same form, so they refuse the same
things. A new web address keeps the old one working: seo's slug watcher knows a
vendor's public path (/vendor/<slug>/) and 301s the old one. An address the
vendor portal uses itself (/vendor/me/, /vendor/apply/) is refused.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.catalog.models import Vendor


class VendorEditTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='vendor-staff', email='vs@x.test', password='x', is_staff=True,
            is_superuser=True,
        )  # fmt: skip
        self.client.force_login(staff)
        self.vendor = Vendor.objects.create(name='Kalda', slug='kalda', description='Old words.')
        self.url = f'/dashboard/marketplace/vendors/{self.vendor.pk}/edit/'

    def _post(self, **fields):
        data = {
            'name': self.vendor.name,
            'slug': self.vendor.slug,
            'description': self.vendor.description,
            'is_active': 'on',
            **fields,
        }
        return self.client.post(self.url, {k: v for k, v in data.items() if v is not None})

    def test_the_vendor_page_and_the_list_link_to_the_form(self):
        detail = self.client.get(f'/dashboard/marketplace/vendors/{self.vendor.pk}/')
        listing = self.client.get('/dashboard/apps/marketplace/vendors/')
        self.assertContains(detail, f'href="{self.url}"')
        self.assertContains(listing, f'href="{self.url}"')

    def test_the_form_shows_the_vendor(self):
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'value="Kalda"')
        self.assertContains(page, 'Old words.')

    def test_saving_changes_the_vendor(self):
        response = self._post(name='Kalda Studio', description='New words.', is_active=None)
        self.assertEqual(response.status_code, 302)
        self.vendor.refresh_from_db()
        self.assertEqual(
            (self.vendor.name, self.vendor.description, self.vendor.is_active),
            ('Kalda Studio', 'New words.', False),
        )

    def test_a_new_address_keeps_the_old_one_working(self):
        self._post(slug='kalda-studio')
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.slug, 'kalda-studio')
        old = self.client.get('/vendor/kalda/')
        self.assertEqual(old.status_code, 301)
        self.assertTrue(old['Location'].endswith('/vendor/kalda-studio/'))

    def test_an_address_another_vendor_has_is_refused(self):
        Vendor.objects.create(name='Other', slug='other')
        response = self._post(slug='other')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Another vendor already has this address.')
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.slug, 'kalda')

    def test_an_address_the_vendor_portal_uses_is_refused(self):
        for slug in ('me', 'apply'):
            response = self._post(slug=slug)
            self.assertContains(response, 'The vendor portal uses this address.')
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.slug, 'kalda')


class VendorToolTests(TestCase):
    def setUp(self):
        Vendor.objects.create(name='Kalda', slug='kalda')
        Vendor.objects.create(name='Probotanic', slug='probotanic', is_active=False)

    def test_linda_can_list_vendors(self):
        from core.agents import agent_registry

        tool = agent_registry.get_tool('vendors.list')
        output = tool.invoke({}).output
        self.assertEqual({v['slug'] for v in output['vendors']}, {'kalda', 'probotanic'})
        self.assertEqual(tool.invoke({'active': True}).output['count'], 1)

    def test_linda_updates_a_vendor_through_the_same_form_and_asks_first(self):
        from core.agents import agent_registry

        tool = agent_registry.get_tool('vendors.update')
        self.assertTrue(tool.requires_approval)
        tool.invoke({'vendor': 'kalda', 'name': 'Kalda Studio', 'is_active': False})
        vendor = Vendor.objects.get(slug='kalda')
        self.assertEqual((vendor.name, vendor.is_active), ('Kalda Studio', False))

    def test_linda_gets_the_forms_refusal(self):
        from core.agents import agent_registry
        from core.agents.tools import ToolError

        with self.assertRaisesMessage(ToolError, 'Another vendor already has this address.'):
            agent_registry.get_tool('vendors.update').invoke(
                {'vendor': 'kalda', 'slug': 'probotanic'}
            )
