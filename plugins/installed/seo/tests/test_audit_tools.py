"""Linda's index-rule, title-pattern and site-audit tools (v0.164.0).

Each write goes through the service the dashboard page uses
(`services/index_rules.py`, `services/templating.py`,
`services/site_audit.queue_site_audit`), so a change Linda proposes is refused
for the same reasons a merchant's would be. Writes carry `requires_approval`:
the first attempt is refused at the gate and the merchant's own "yes" spends it.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from core.agents.tools import ToolError
from core.assistant import gates
from core.assistant.gates import LINDA_SCOPES
from plugins.installed.seo.models import IndexRule, SeoTemplate
from plugins.installed.seo.services import site_audit

READS = ('seo.index_rules', 'seo.templates', 'seo.audit_results')
WRITES = (
    'seo.set_index_rule',
    'seo.delete_index_rule',
    'seo.set_template',
    'seo.delete_template',
    'seo.run_site_audit',
)


def _tool(name):
    from morpheus.core import agent_registry

    tool = agent_registry.get_tool(name)
    assert tool is not None, f'{name} is not registered'
    return tool


def _gate(tool, args, *, human_message, key='seo-tools'):
    return gates.gate_reason(
        tool=tool,
        tool_name=tool.name,
        args=args,
        scopes=LINDA_SCOPES,
        context={},
        conversation_key=key,
        human_message=human_message,
    )


class RegistrationTests(TestCase):
    def test_each_tool_is_seos_with_the_right_scope(self):
        from morpheus.core import agent_registry

        for name in READS:
            with self.subTest(name=name):
                tool = _tool(name)
                self.assertEqual(agent_registry._tool_owners.get(name), 'seo')
                self.assertEqual(list(tool.scopes), ['seo.read'])
                self.assertFalse(tool.requires_approval)
        for name in WRITES:
            with self.subTest(name=name):
                tool = _tool(name)
                self.assertEqual(agent_registry._tool_owners.get(name), 'seo')
                self.assertEqual(list(tool.scopes), ['seo.write'])
                self.assertTrue(tool.requires_approval)

    def test_the_scopes_are_in_the_vocabulary_and_lindas_profile(self):
        from plugins.installed.agent_mcp.scopes import AVAILABLE_SCOPES

        for scope in ('seo.read', 'seo.write'):
            self.assertIn(scope, AVAILABLE_SCOPES)
            self.assertIn(scope, LINDA_SCOPES)

    def test_lindas_catalogue_offers_them(self):
        import types

        from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue

        user = types.SimpleNamespace(is_staff=True, is_superuser=False, pk=1)
        turn = LindaTurn(user=user, conversation_key='user:1', mode_slug='general')
        names = {t.name for t in catalogue(turn)}
        for name in READS + WRITES:
            self.assertIn(name, names)


class ReadTests(TestCase):
    def test_index_rules_lists_the_rows(self):
        IndexRule.objects.create(param='utm_*', policy='consolidate', note='tracking')
        rules = _tool('seo.index_rules').invoke({}).output['rules']
        self.assertEqual(
            [(r['param'], r['policy'], r['note']) for r in rules],
            [('utm_*', 'consolidate', 'tracking')],
        )

    def test_templates_lists_rows_and_the_tokens_a_pattern_can_use(self):
        SeoTemplate.objects.create(kind='product', field='title', template='{name} | shop')
        out = _tool('seo.templates').invoke({}).output
        self.assertEqual([t['template'] for t in out['templates']], ['{name} | shop'])
        for token in ('{name}', '{site_name}', '{price}', '{category}'):
            self.assertIn(token, out['tokens'])
        self.assertIn('product', out['kinds'])

    def test_audit_results_before_and_after_a_scan(self):
        cache.delete(site_audit.CACHE_KEY)
        self.addCleanup(cache.delete, site_audit.CACHE_KEY)
        empty = _tool('seo.audit_results').invoke({})
        self.assertIsNone(empty.output['ran_at'])
        self.assertIn('seo.run_site_audit', empty.display)

        examples = [f'/products/p-{i}/' for i in range(25)]
        cache.set(
            site_audit.CACHE_KEY,
            {
                'generated_at': '2026-11-12T09:00:00+00:00',
                'partial': True,
                'pages_checked': 25,
                'score': 71,
                'findings': [
                    {
                        'code': 'markup_price_stale',
                        'severity': site_audit.CRITICAL,
                        'title': 'Stale price',
                        'why': '…',
                        'count': 25,
                        'examples': examples,
                        'fix_label': 'Products',
                        'fix_url': '/dashboard/products/',
                    }
                ],
                'checks': {'orphans_checked': False, 'orphans_skipped_because': 'time limit'},
                'measured': {'total_s': 12.5},
            },
        )
        out = _tool('seo.audit_results').invoke({}).output
        self.assertEqual(out['ran_at'], '2026-11-12T09:00:00+00:00')
        self.assertTrue(out['partial'])
        self.assertEqual(out['summary'], {site_audit.CRITICAL: 1})
        finding = out['findings'][0]
        self.assertEqual((finding['code'], finding['count']), ('markup_price_stale', 25))
        self.assertEqual(finding['pages'], examples[:20])
        self.assertEqual(out['checks']['orphans_skipped_because'], 'time limit')


class ConsentTests(TestCase):
    """Writes wait for the merchant's own yes, then do what the dashboard does."""

    def setUp(self):
        cache.clear()

    def test_an_index_rule_waits_for_a_yes_then_applies(self):
        tool = _tool('seo.set_index_rule')
        args = {'param': 'sort', 'policy': 'noindex'}
        self.assertIn('approval_required', _gate(tool, args, human_message='tidy the urls') or '')
        self.assertFalse(IndexRule.objects.exists())
        self.assertIsNone(_gate(tool, args, human_message='yes'))
        out = tool.invoke(args).output
        self.assertEqual((out['rule']['param'], out['rule']['policy']), ('sort', 'noindex'))
        self.assertTrue(out['created'])
        # The same parameter again changes that row, not a second one.
        tool.invoke({'param': 'SORT', 'policy': 'consolidate'})
        self.assertEqual(
            list(IndexRule.objects.values_list('param', 'policy')), [('sort', 'consolidate')]
        )

    def test_a_pattern_waits_for_a_yes_then_applies(self):
        tool = _tool('seo.set_template')
        args = {'template': '{name} | {site_name}', 'kind': 'product'}
        self.assertIn('approval_required', _gate(tool, args, human_message='better titles') or '')
        self.assertIsNone(_gate(tool, args, human_message='yes, do it'))
        tool.invoke(args)
        self.assertEqual(SeoTemplate.objects.get().template, '{name} | {site_name}')

    def test_deletes_wait_for_a_yes(self):
        rule = IndexRule.objects.create(param='color', policy='noindex')
        tool = _tool('seo.delete_index_rule')
        self.assertIn('approval_required', _gate(tool, {'param': 'color'}, human_message='x') or '')
        self.assertIsNone(_gate(tool, {'param': 'color'}, human_message='ok'))
        tool.invoke({'param': 'color'})
        self.assertFalse(IndexRule.objects.filter(pk=rule.pk).exists())
        with self.assertRaises(ToolError):
            tool.invoke({'param': 'color'})

        pattern = SeoTemplate.objects.create(kind='product', field='title', template='{name}')
        delete = _tool('seo.delete_template')
        args = {'template_id': str(pattern.pk)}
        self.assertIn('approval_required', _gate(delete, args, human_message='x') or '')
        self.assertIsNone(_gate(delete, args, human_message='yes'))
        delete.invoke(args)
        self.assertFalse(SeoTemplate.objects.exists())


class RefusalTests(TestCase):
    def test_an_unknown_token_is_refused_with_the_valid_ones(self):
        with self.assertRaises(ToolError) as caught:
            _tool('seo.set_template').invoke({'template': '{nmae} | shop', 'kind': 'product'})
        message = str(caught.exception)
        self.assertIn('Unknown token {nmae}', message)
        self.assertIn('{name}', message)
        self.assertFalse(SeoTemplate.objects.exists())

    def test_filters_and_fallback_literals_are_not_tokens(self):
        _tool('seo.set_template').invoke(
            {'template': '{name|truncate:40|title}[ in {category|"Shop"}]', 'kind': 'product'}
        )
        self.assertEqual(SeoTemplate.objects.count(), 1)

    def test_a_metafield_key_the_shop_holds_is_a_token(self):
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield

        product = Product.objects.create(name='Token Probe', slug='token-probe', price=10)
        tool = _tool('seo.set_template')
        with self.assertRaises(ToolError):
            tool.invoke({'template': '{name} by {author}', 'kind': 'product'})
        Metafield.objects.create(
            content_type=ContentType.objects.get_for_model(Product),
            object_id=str(product.pk),
            namespace='book',
            key='author',
            value='Ursula K. Le Guin',
        )
        tool.invoke({'template': '{name} by {author}', 'kind': 'product'})
        self.assertEqual(SeoTemplate.objects.get().template, '{name} by {author}')

    def test_the_page_number_takes_no_rule(self):
        for param in ('page', 'page*', 'p*', 'PAGE'):
            with self.subTest(param=param), self.assertRaises(ToolError) as caught:
                _tool('seo.set_index_rule').invoke({'param': param, 'policy': 'block'})
            self.assertIn('page number', str(caught.exception))
        self.assertFalse(IndexRule.objects.exists())

    def test_an_unknown_policy_is_refused(self):
        with self.assertRaises(ToolError):
            _tool('seo.set_index_rule').invoke({'param': 'sort', 'policy': 'delete'})


class RunSiteAuditTests(TestCase):
    def setUp(self):
        for key in (site_audit.CACHE_KEY, site_audit.RUNNING_KEY, site_audit.QUEUED_KEY):
            cache.delete(key)
            self.addCleanup(cache.delete, key)
        patcher = patch('plugins.installed.seo.tasks.site_audit_task.delay')
        self.delay = patcher.start()
        self.addCleanup(patcher.stop)

    def test_it_queues_once_and_refuses_a_second_run(self):
        tool = _tool('seo.run_site_audit')
        self.assertTrue(tool.invoke({}).output['queued_at'])
        self.assertEqual(self.delay.call_count, 1)
        with self.assertRaises(ToolError) as caught:
            tool.invoke({})
        self.assertIn('queued less than ten minutes ago', str(caught.exception))
        self.assertEqual(self.delay.call_count, 1)

    def test_a_scan_that_finished_minutes_ago_is_not_repeated(self):
        recent = (timezone.now() - timezone.timedelta(minutes=3)).isoformat()
        cache.set(site_audit.CACHE_KEY, {'generated_at': recent, 'findings': []})
        with self.assertRaises(ToolError) as caught:
            _tool('seo.run_site_audit').invoke({})
        self.assertIn('3 minute(s) ago', str(caught.exception))
        self.delay.assert_not_called()

    def test_an_older_scan_can_be_repeated(self):
        old = (timezone.now() - timezone.timedelta(minutes=11)).isoformat()
        cache.set(site_audit.CACHE_KEY, {'generated_at': old, 'findings': []})
        _tool('seo.run_site_audit').invoke({})
        self.assertEqual(self.delay.call_count, 1)

    def test_a_running_scan_is_not_doubled(self):
        cache.set(site_audit.RUNNING_KEY, timezone.now().isoformat(), 60)
        with self.assertRaises(ToolError) as caught:
            _tool('seo.run_site_audit').invoke({})
        self.assertIn('already running', str(caught.exception))
        self.delay.assert_not_called()

    def test_the_dashboard_button_refuses_the_same_way(self):
        user = get_user_model().objects.create_user(
            username='audit@example.com',
            email='audit@example.com',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)
        cache.set(site_audit.RUNNING_KEY, timezone.now().isoformat(), 60)
        response = self.client.post('/dashboard/seo/site-audit/run/', follow=True)
        self.assertContains(response, 'already running')
        self.delay.assert_not_called()


class DashboardSharesTheServiceTests(TestCase):
    """The templates page refuses an unknown token with the same words as the tool."""

    def test_the_templates_page_refuses_an_unknown_token(self):
        user = get_user_model().objects.create_user(
            username='seo2@example.com', email='seo2@example.com', is_staff=True, is_superuser=True
        )
        self.client.force_login(user)
        response = self.client.post(
            '/dashboard/seo/templates/',
            {'action': 'create', 'kind': 'product', 'field': 'title', 'template': '{nmae}'},
            follow=True,
        )
        self.assertContains(response, 'Unknown token {nmae}')
        self.assertFalse(SeoTemplate.objects.exists())

    def test_the_index_rules_page_refuses_the_page_number(self):
        user = get_user_model().objects.create_user(
            username='seo3@example.com', email='seo3@example.com', is_staff=True, is_superuser=True
        )
        self.client.force_login(user)
        from django.urls import reverse

        response = self.client.post(
            reverse('seo_dashboard:index_rules'),
            {'action': 'create', 'param': 'page*', 'policy': 'block'},
            follow=True,
        )
        self.assertContains(response, 'page number')
        self.assertFalse(IndexRule.objects.exists())
