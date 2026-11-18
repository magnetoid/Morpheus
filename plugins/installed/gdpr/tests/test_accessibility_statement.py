"""The seeded accessibility statement covers what the EAA asks (v0.178.0).

The European Accessibility Act (Directive (EU) 2019/882) applies to online stores
from 28 June 2025. Annex V asks for a description of the service, of how it works and
of how it meets the accessibility requirements, and Art. 13(2) for the information in
writing and by voice. The seed fills the store's name and contact from its settings;
the 0003 migration replaces the old seed's text on a store, and leaves a page the
merchant wrote alone.
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

from django.apps import apps
from django.test import TestCase

from core.models import StoreSettings
from plugins.installed.cms.models import Page
from plugins.installed.gdpr import services

migration = importlib.import_module(
    'plugins.installed.gdpr.migrations.0003_accessibility_statement'
)

_OLD = migration._OLD_TEMPLATE.replace('{opening}', migration._OLD_SEEDS[1])


def _settings(**values) -> StoreSettings:
    row = StoreSettings.objects.first() or StoreSettings.objects.create()
    for key, value in values.items():
        setattr(row, key, value)
    row.save()
    return row


class StatementTests(TestCase):
    def test_it_covers_annex_v(self):
        body = services.accessibility_body()
        for heading in (
            '<h3>The service</h3>',
            '<h3>How it works</h3>',
            '<h3>How we meet the accessibility requirements</h3>',
            '<h3>How we check it</h3>',
            '<h3>Known limitations</h3>',
            '<h3>Contact us</h3>',
        ):
            self.assertIn(heading, body)
        self.assertIn('EN 301 549', body)
        self.assertIn('WCAG) 2.2 at level AA', body)
        self.assertIn('Directive (EU) 2019/882', body)
        self.assertIn('This statement was prepared on', body)
        self.assertNotIn('{', body)

    def test_the_store_name_and_contact_come_from_its_settings(self):
        _settings(
            store_name='Lumen <Works>',
            contact_email='help@lumen.test',
            support_phone='+382 20 123 456',
        )
        body = services.accessibility_body()
        self.assertIn('Lumen &lt;Works&gt; is an online store.', body)
        self.assertIn('href="mailto:help@lumen.test"', body)
        # By voice too (Art. 13(2)), when the store has a phone number.
        self.assertIn('by phone on +382 20 123 456', body)

    def test_without_settings_it_names_no_default(self):
        _settings(store_name=StoreSettings._meta.get_field('store_name').default)
        body = services.accessibility_body()
        self.assertIn('This is an online store.', body)
        self.assertNotIn('Morpheus Store', body)
        self.assertNotIn('by phone', body)


class ReplaceUntouchedSeedTests(TestCase):
    def setUp(self):
        Page.objects.filter(slug='accessibility').delete()

    def _page(self, body: str) -> Page:
        return Page.objects.create(
            slug='accessibility', title='Accessibility Statement', body=body, state='published'
        )

    def test_the_old_seed_is_replaced_whatever_email_it_named(self):
        for opening in migration._OLD_SEEDS:
            # As the seed stored it (through the page's sanitiser), and as a store
            # seeded before the sanitiser existed holds it (raw).
            for sanitised in (True, False):
                with self.subTest(opening=opening[:40], sanitised=sanitised):
                    Page.objects.filter(slug='accessibility').delete()
                    old = migration._OLD_TEMPLATE.replace('{opening}', opening)
                    page = self._page(old.replace('{email}', 'shop@old.test'))
                    if not sanitised:
                        Page.objects.filter(pk=page.pk).update(body=old.replace('{email}', 'a@b.c'))
                    migration.replace_untouched(apps, None)
                    page.refresh_from_db()
                    self.assertIn('<h3>How it works</h3>', page.body)
                    self.assertNotIn('style=', page.body)  # stored as the sanitiser leaves it
                    self.assertEqual(page.excerpt, services.ACCESSIBILITY_EXCERPT)

    def test_a_page_the_merchant_wrote_stays(self):
        page = self._page(_OLD.replace('{email}', 'a@b.test').replace('as a priority', 'in a day'))
        before = Page.objects.get(pk=page.pk).body
        migration.replace_untouched(apps, None)
        page.refresh_from_db()
        self.assertEqual(page.body, before)

    def test_no_page_is_created_and_nothing_fails(self):
        migration.replace_untouched(apps, None)
        self.assertFalse(Page.objects.filter(slug='accessibility').exists())
        self._page(_OLD.replace('{email}', 'a@b.test'))
        with patch.object(services, 'accessibility_body', side_effect=RuntimeError('boom')):
            migration.replace_untouched(apps, None)  # fail-soft, like the seed
