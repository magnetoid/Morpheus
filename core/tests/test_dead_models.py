"""Apps Wave 1: dead models leave Django's state in one release and their tables in
the next, so the release before still runs (docs/plans/apps-consolidation-2026-10.md)."""

from __future__ import annotations

from django.apps import apps
from django.db import connection
from django.test import TestCase

FORGOTTEN = {
    'customers': ('WishList', 'WishListItem'),
    'ai_assistant': ('AgentMemory', 'DemandForecast', 'AIExperiment', 'PromptTemplate'),
    'marketing': ('Redirect',),
    'observability': ('ErrorEvent',),
    'morpheus_brain': ('DailyReport', 'ReportReference'),
    'loyalty_points': ('Referral',),
}
TABLES = (
    'customers_wishlist',
    'customers_wishlistitem',
    'ai_assistant_agentmemory',
    'ai_assistant_demandforecast',
    'ai_assistant_aiexperiment',
    'ai_assistant_prompttemplate',
    'marketing_redirect',
    'observability_errorevent',
    'morpheus_brain_dailyreport',
    'morpheus_brain_reportreference',
    'loyalty_referral',
)


class DeadModelsTests(TestCase):
    def test_the_models_are_gone(self):
        for label, names in FORGOTTEN.items():
            for name in names:
                with self.assertRaises(LookupError, msg=f'{label}.{name}'):
                    apps.get_model(label, name)

    def test_an_ai_interaction_no_longer_names_a_prompt_template(self):
        fields = {
            f.name for f in apps.get_model('ai_assistant', 'AIInteraction')._meta.get_fields()
        }
        self.assertNotIn('prompt_template', fields)

    def test_their_tables_stay_for_the_release_before(self):
        # Release A changes state only: v0.121.0, put back by the guard, finds every table.
        present = set(connection.introspection.table_names())
        self.assertEqual([t for t in TABLES if t not in present], [])
