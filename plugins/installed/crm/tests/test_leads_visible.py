"""Leads can be found: a CRM Leads tab, and Contacts → Leads for the ones with no account.

The CRM overview counted open leads while no page in the menu listed them: the
Leads tab had been taken out in favour of Contacts, which lists accounts only, so
dotbooks showed 341 open leads and nowhere to see one.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from plugins.installed.admin_dashboard.tests.test_disable_safety import disabled
from plugins.installed.crm.models import Lead

User = get_user_model()


class _StaffCase(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='leads-staff', email='leads-staff@example.test', password='x', is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.staff)


class CrmLeadsTabTests(_StaffCase):
    def test_every_lead_is_reachable_page_by_page(self):
        Lead.objects.bulk_create(
            [Lead(email=f'bulk-lead-{i:03d}@example.test', source='newsletter') for i in range(230)]
        )
        first = self.client.get('/dashboard/crm/leads/')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.context['page_obj'].paginator.count, 230)
        last_page = first.context['page_obj'].paginator.num_pages
        last = self.client.get(f'/dashboard/crm/leads/?page={last_page}')
        self.assertContains(last, 'bulk-lead-000@example.test')

    def test_search_and_status_narrow_the_list(self):
        Lead.objects.create(email='ana-marker@example.test', first_name='Ana', status='new')
        Lead.objects.create(email='bo-marker@example.test', status='lost')
        found = self.client.get('/dashboard/crm/leads/?q=ana-marker')
        self.assertContains(found, 'ana-marker@example.test')
        self.assertNotContains(found, 'bo-marker@example.test')
        open_only = self.client.get('/dashboard/crm/leads/?status=open')
        self.assertContains(open_only, 'ana-marker@example.test')
        self.assertNotContains(open_only, 'bo-marker@example.test')

    def test_overview_number_opens_the_same_leads(self):
        Lead.objects.create(email='open-one@example.test', status='new')
        Lead.objects.create(email='open-two@example.test', status='qualified')
        Lead.objects.create(email='gone@example.test', status='lost')
        home = self.client.get('/dashboard/crm/')
        self.assertEqual(home.context['metrics']['open_leads'], 2)
        self.assertContains(home, 'href="/dashboard/crm/leads/?status=open"')
        listed = self.client.get('/dashboard/crm/leads/?status=open')
        self.assertEqual(listed.context['page_obj'].paginator.count, 2)


class ContactsLeadsTabTests(_StaffCase):
    def setUp(self):
        super().setUp()
        Lead.objects.create(email='no-account-marker@example.test', source='newsletter')
        Lead.objects.create(email='converted-marker@example.test', status='converted')
        User.objects.create_user(username='has-account', email='has-account-marker@example.test')
        Lead.objects.create(email='HAS-ACCOUNT-marker@example.test', source='newsletter')

    def test_leads_tab_lists_leads_without_an_account(self):
        response = self.client.get('/dashboard/customers/?source=lead_form')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no-account-marker@example.test')
        self.assertContains(response, 'data-lead-row', count=1)
        self.assertNotContains(response, 'converted-marker@example.test')
        tab = next(t for t in response.context['source_tabs'] if t['value'] == 'lead_form')
        self.assertEqual(tab['count'], 1)

    def test_search_reaches_the_leads(self):
        response = self.client.get('/dashboard/customers/?source=lead_form&q=nobody-matches')
        self.assertNotContains(response, 'no-account-marker@example.test')

    def test_other_tabs_still_list_accounts(self):
        response = self.client.get('/dashboard/customers/')
        self.assertContains(response, 'has-account-marker@example.test')
        self.assertNotContains(response, 'data-lead-row')

    def test_leads_leave_contacts_with_the_crm(self):
        with disabled('crm'):
            response = self.client.get('/dashboard/customers/?source=lead_form')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'no-account-marker@example.test')
        self.assertNotContains(response, 'data-lead-row')
