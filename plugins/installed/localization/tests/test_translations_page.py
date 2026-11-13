"""Settings → General → Translations and its editor (v0.160.0).

Before v0.160.0 the app's two pages did nothing: the list was always empty and the
Languages page saved a setting nothing read.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from djmoney.money import Money

from core.agents.llm import LLMResponse, MockLLMProvider
from core.i18n.models import Translation
from core.i18n.services import set_translation

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}
INDEX = '/dashboard/apps/localization/translations/'


def _user(name, *, staff):
    return get_user_model().objects.create_user(
        username=name, email=f'{name}@example.test', password='x', is_staff=staff
    )


def _product(slug='harbour-map', **extra):
    from plugins.installed.catalog.models import Product

    return Product.objects.create(
        name=extra.pop('name', 'Harbour Map'),
        slug=slug,
        sku=slug.upper()[:30],
        price=Money(Decimal('9.00'), 'EUR'),
        status='active',
        description=extra.pop('description', '<p>Every quay, drawn.</p>'),
        **extra,
    )


def _editor(product):
    return f'{INDEX}catalog.product/{product.pk}/sr/'


def _provider(payload: dict) -> MockLLMProvider:
    return MockLLMProvider([LLMResponse(text=json.dumps(payload), model='mock-1')])


@override_settings(**BILINGUAL)
class GateTests(TestCase):
    def setUp(self):
        self.product = _product()

    def test_a_visitor_is_sent_to_sign_in(self):
        for url in (INDEX, _editor(self.product)):
            self.assertEqual(Client().get(url).status_code, 302, url)

    def test_staff_without_the_capability_are_refused_when_roles_are_enforced(self):
        client = Client()
        client.force_login(_user('clerk', staff=True))
        for url in (INDEX, _editor(self.product)):
            with (
                patch('core.authz.enforcement_mode', return_value='enforce'),
                patch('core.authz.has_capability', return_value=False),
            ):
                self.assertEqual(client.get(url).status_code, 403, url)

    def test_staff_with_the_capability_see_both(self):
        client = Client()
        client.force_login(_user('manager', staff=True))
        page = client.get(INDEX)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Products')
        self.assertContains(page, 'Harbour Map')
        editor = client.get(_editor(self.product))
        self.assertEqual(editor.status_code, 200)
        self.assertContains(editor, 'Every quay, drawn.')

    def test_a_saving_member_without_write_is_refused(self):
        client = Client()
        client.force_login(_user('reader', staff=True))
        with (
            patch('core.authz.enforcement_mode', return_value='enforce'),
            patch(
                'core.authz.has_capability',
                side_effect=lambda user, cap, **kw: cap == 'system.read',
            ),
        ):
            response = client.post(_editor(self.product), {'action': 'save', 'f-name': 'Mapa'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Translation.objects.exists())


class SingleLanguageTests(TestCase):
    @override_settings(LANGUAGES=[('en', 'English')], LANGUAGE_CODE='en')
    def test_a_one_language_store_is_told_so(self):
        client = Client()
        client.force_login(_user('owner', staff=True))
        self.assertContains(client.get(INDEX), 'offered in one language')


@override_settings(**BILINGUAL)
class EditorTests(TestCase):
    def setUp(self):
        cache.clear()
        self.product = _product()
        self.client = Client()
        self.client.force_login(_user('owner', staff=True))

    def test_save_writes_reviewed_text_and_an_empty_field_deletes_it(self):
        response = self.client.post(
            _editor(self.product),
            {'action': 'save', 'f-name': 'Lučka mapa', 'f-description': '<p>Svaki gat.</p>'},
        )
        self.assertEqual(response.status_code, 302)
        rows = {r.field: r for r in Translation.objects.filter(language_code='sr')}
        self.assertEqual(rows['name'].value, 'Lučka mapa')
        self.assertTrue(rows['name'].reviewed)
        self.assertFalse(rows['name'].is_machine_translated)
        self.client.post(_editor(self.product), {'action': 'save', 'f-name': 'Lučka mapa'})
        self.assertFalse(Translation.objects.filter(field='description').exists())

    def test_a_draft_is_marked_and_saving_it_keeps_its_provenance(self):
        set_translation(
            self.product, 'name', 'sr', 'Mapa luke', machine_translated=True, reviewed=False
        )
        page = self.client.get(_editor(self.product))
        self.assertContains(page, 'Draft — not shown to shoppers until you save it')
        self.client.post(
            _editor(self.product),
            {'action': 'save', 'f-name': 'Mapa luke', 'f-description': '<p>Gat.</p>'},
        )
        row = Translation.objects.get(field='name')
        self.assertTrue(row.reviewed)
        self.assertTrue(row.is_machine_translated)

    def test_draft_with_ai_writes_an_unreviewed_draft(self):
        payload = {'name': 'Mapa luke', 'description': '<p>Svaki gat.</p>'}
        with patch('core.agents.llm.get_llm_provider', return_value=_provider(payload)):
            self.client.post(_editor(self.product), {'action': 'draft'})
        rows = {r.field: r for r in Translation.objects.filter(language_code='sr')}
        self.assertEqual(rows['name'].value, 'Mapa luke')
        self.assertFalse(rows['name'].reviewed)
        self.assertTrue(rows['name'].is_machine_translated)

    def test_draft_the_missing_ones_queues_them(self):
        _product('second-map', name='Second Map')
        payload = {'name': 'Mapa', 'description': '<p>Gat.</p>'}
        provider = MockLLMProvider(
            [LLMResponse(text=json.dumps(payload)), LLMResponse(text=json.dumps(payload))]
        )
        with patch('core.agents.llm.get_llm_provider', return_value=provider):
            response = self.client.post(
                INDEX, {'action': 'draft_missing', 'kind': 'catalog.product', 'language': 'sr'}
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Translation.objects.filter(field='name', reviewed=False).count(), 2)
        page = self.client.get(f'{INDEX}?kind=catalog.product&language=sr&status=draft')
        self.assertContains(page, 'Second Map')

    def test_a_draft_button_drafts_its_own_row_not_the_filtered_list(self):
        # Each summary row's form posts its kind and language to the filtered list's url.
        with patch('plugins.installed.localization.views.i18n_queue', return_value=1) as queue:
            response = self.client.post(
                f'{INDEX}?kind=cms.page&language=sr',
                {'action': 'draft_missing', 'kind': 'catalog.product', 'language': 'sr'},
            )
        queue.assert_called_once_with('catalog.product', 'sr')
        self.assertIn('kind=catalog.product', response['Location'])
