"""gdpr plugin — self-service data rights, disable-safety, legal-page seeding.

Covers the plugin contract's four litmus tests for this feature:
  * DSR export streams a ZIP of the customer's data (delegated to
    customers.services.gather_customer_data) + records a DataRequest.
  * DSR erasure anonymises the account (customers.services.anonymise_customer)
    + records a DataRequest.
  * DISABLE test — the account tile, footer legal links, and settings panel
    are contributed only while the plugin is active; they vanish on disable.
  * DELETE-the-dir litmus — the old dead views left no dangling reference in
    the storefront account module.
"""

from __future__ import annotations

import io
import json
import zipfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.http import Http404
from django.test import TestCase

from core.models import StoreSettings
from plugins.installed.gdpr.models import DataRequest
from plugins.installed.gdpr.services import gdpr_required, seed_legal_pages
from plugins.registry import plugin_registry


def _customer(email='dsr@example.com'):
    return get_user_model().objects.create_user(username=email, email=email, password='pw')


class DataExportTests(TestCase):
    def test_export_streams_zip_with_customer_data(self):
        c = _customer()
        self.client.force_login(c)
        resp = self.client.post('/account/data-export/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')

        zf = zipfile.ZipFile(io.BytesIO(resp.getvalue()))
        names = zf.namelist()
        self.assertIn('account.json', names)
        account = json.loads(zf.read('account.json'))
        self.assertEqual(account['email'], c.email)

        req = DataRequest.objects.get(customer=c, kind='export')
        self.assertEqual(req.status, 'completed')
        self.assertIsNotNone(req.completed_at)

    def test_export_get_requires_login(self):
        resp = self.client.get('/account/data-export/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])


class ErasureTests(TestCase):
    def test_erasure_anonymises_via_customers_service(self):
        c = _customer('erase-me@example.com')
        self.client.force_login(c)
        resp = self.client.post('/account/delete/', {'confirm_email': 'erase-me@example.com'})
        self.assertEqual(resp.status_code, 302)

        c.refresh_from_db()
        self.assertFalse(c.is_active)
        self.assertEqual(c.first_name, 'Deleted')
        self.assertNotIn('erase-me', c.email)

        req = DataRequest.objects.get(kind='erasure')
        self.assertEqual(req.status, 'completed')

    def test_erasure_rejects_wrong_email(self):
        c = _customer('keep-me@example.com')
        self.client.force_login(c)
        resp = self.client.post('/account/delete/', {'confirm_email': 'wrong@example.com'})
        self.assertEqual(resp.status_code, 200)  # re-render with error, no redirect
        c.refresh_from_db()
        self.assertTrue(c.is_active)
        self.assertFalse(DataRequest.objects.filter(kind='erasure').exists())


class GateTests(TestCase):
    """The gdpr_required() master-switch gate (moved here from storefront)."""

    def setUp(self):
        cache.delete('morph:gdpr_enabled')

    def _set_gdpr(self, on: bool):
        s = StoreSettings.objects.first() or StoreSettings()
        s.gdpr_enabled = on
        s.save()
        cache.delete('morph:gdpr_enabled')

    def test_gate_default_passes(self):
        gdpr_required()  # no store row → default True → does not raise

    def test_gate_raises_when_disabled(self):
        self._set_gdpr(False)
        with self.assertRaises(Http404):
            gdpr_required()

    def test_privacy_hub_404s_when_disabled(self):
        c = _customer('gate@example.com')
        self.client.force_login(c)
        self._set_gdpr(False)
        resp = self.client.get('/account/privacy/')
        self.assertEqual(resp.status_code, 404)


class DisableTests(TestCase):
    """Every surface the plugin contributes must vanish when it is disabled."""

    def _gdpr_blocks(self, slot):
        return [b for b in plugin_registry.storefront_blocks_for(slot) if b.plugin == 'gdpr']

    def test_surfaces_present_while_active(self):
        self.assertTrue(self._gdpr_blocks('account_nav'), 'account tile missing while active')
        self.assertTrue(self._gdpr_blocks('footer_legal'), 'footer links missing while active')
        self.assertIsNotNone(plugin_registry.settings_panel('gdpr'))

    def test_surfaces_vanish_on_disable(self):
        self.addCleanup(plugin_registry.activate, 'gdpr')
        plugin_registry.deactivate('gdpr')
        self.assertEqual(self._gdpr_blocks('account_nav'), [])
        self.assertEqual(self._gdpr_blocks('footer_legal'), [])
        self.assertIsNone(plugin_registry.settings_panel('gdpr'))


class LegalPageSeedTests(TestCase):
    def test_seed_is_idempotent(self):
        from plugins.installed.cms.models import Page

        first = seed_legal_pages()
        self.assertEqual(first['created'], 3)
        for slug in ('privacy', 'terms', 'imprint'):
            self.assertTrue(Page.objects.filter(slug=slug, state='published').exists())
        # LLM providers must be disclosed on the privacy page (Art. 13 recipients).
        privacy = Page.objects.get(slug='privacy')
        self.assertIn('LLM', privacy.body)

        second = seed_legal_pages()
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['skipped'], 3)

    def test_management_command_runs(self):
        call_command('seed_legal_pages')
        from plugins.installed.cms.models import Page

        self.assertEqual(Page.objects.filter(slug__in=['privacy', 'terms', 'imprint']).count(), 3)


class DeadCodeLitmusTests(TestCase):
    """Removing the old dead storefront views left no dangling reference."""

    def test_storefront_account_has_no_gdpr_view_orphans(self):
        from plugins.installed.storefront.views import account as acct

        self.assertFalse(hasattr(acct, 'account_data_export'))
        self.assertFalse(hasattr(acct, 'account_delete'))
        self.assertFalse(hasattr(acct, '_gdpr_required'))
