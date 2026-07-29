"""The dashboard-home KPI row, side panels, and setup checklist are
CONTRIBUTED by their owning plugins via the DASHBOARD_KPIS /
DASHBOARD_HOME_PANELS / DASHBOARD_SETUP_STEPS filters, NOT hardcoded in
admin_dashboard — so a disabled plugin's tile never renders. See
docs/plans/dashboard-home-modular.md.
"""

# Lazy imports inside test methods are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from djmoney.money import Money

_HOME_PY = Path(settings.BASE_DIR) / 'plugins/installed/admin_dashboard/views_split/home.py'


class DashboardHomeModularityTests(TestCase):
    def test_home_no_longer_imports_sibling_plugin_models(self):
        # The WHOLE module: with the pulse routes moved to ai_assistant,
        # home.py owns nothing but filter-firing and the email setup step.
        src = _HOME_PY.read_text(encoding='utf-8')
        for plugin in ('orders', 'catalog', 'ai_assistant', 'agent_core', 'inventory'):
            self.assertNotIn(
                f'installed.{plugin}',
                src,
                f'home.py still imports {plugin} — it belongs in that '
                "plugin's dashboard filter subscriber",
            )

    def test_pulse_routes_are_owned_by_ai_assistant(self):
        # Same /dashboard/pulse/... paths as before, registered BY the
        # plugin — so disabling ai_assistant 404s them, and the dashboard
        # no longer owns the names.
        from django.urls import NoReverseMatch, reverse

        self.assertEqual(
            reverse('ai_assistant_dashboard:pulse_refresh'), '/dashboard/pulse/refresh/'
        )
        with self.assertRaises(NoReverseMatch):
            reverse('admin_dashboard:pulse_refresh')

    def test_contributing_plugins_are_subscribed(self):
        from morpheus.core import MorpheusEvents, hook_registry

        def quals(event):
            return {
                getattr(hook_registry._unpack(entry)[1], '__qualname__', '')
                for entry in hook_registry._handlers.get(event, [])
            }

        kpis = quals(MorpheusEvents.DASHBOARD_KPIS)
        self.assertTrue(any('on_dashboard_kpis' in q for q in kpis), 'orders KPI missing')
        self.assertTrue(any('CatalogPlugin' in q for q in kpis), 'catalog KPI missing')

        panels = quals(MorpheusEvents.DASHBOARD_HOME_PANELS)
        for expected in (
            'on_dashboard_panels',  # orders module-level handler
            'CatalogPlugin',
            'AIAssistantPlugin',
            'AgentCorePlugin',
            'InventoryPlugin',
        ):
            self.assertTrue(any(expected in q for q in panels), f'{expected} not on panels')

        steps = quals(MorpheusEvents.DASHBOARD_SETUP_STEPS)
        for expected in ('CatalogPlugin', 'on_setup_steps', 'AIAssistantPlugin'):
            self.assertTrue(any(expected in q for q in steps), f'{expected} not on steps')

    def test_kpis_and_recent_orders_contributed_end_to_end(self):
        from django.test import RequestFactory

        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.admin_dashboard.views_split._shared import _resolve_date_range
        from plugins.installed.orders.models import Order

        order = Order.objects.create(
            email='c@example.com',
            subtotal=Money(Decimal('10'), 'USD'),
            total=Money(Decimal('10'), 'USD'),
        )
        date_range = _resolve_date_range(RequestFactory().get('/dashboard/'))

        metrics = hook_registry.filter(
            MorpheusEvents.DASHBOARD_KPIS, value=[], date_range=date_range
        )
        labels = [m['label'] for m in metrics]
        self.assertIn('Total sales', labels)
        self.assertIn('Orders', labels)
        self.assertIn('Active products', labels)

        panels = hook_registry.filter(
            MorpheusEvents.DASHBOARD_HOME_PANELS, value={}, date_range=date_range
        )
        self.assertIn(order, panels.get('recent_orders', []))
        self.assertIn('ai_summary', panels)

    def test_setup_steps_contributed_and_ordered(self):
        from plugins.installed.admin_dashboard.views_split.home import _compute_setup_steps

        steps = _compute_setup_steps()
        keys = [s['key'] for s in steps]
        self.assertEqual(keys, ['product', 'order', 'ai', 'email'])
        # No products/orders exist → first two steps undone.
        self.assertFalse(steps[0]['done'])
        self.assertFalse(steps[1]['done'])


class SetupChecklistSkipTests(TestCase):
    """The first-run 'Set up your store' checklist can be skipped for good."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.test import Client

        self.client = Client()
        u = get_user_model().objects.create_user(
            username='setupstaff', email='setup@x.test', password='pw', is_staff=True
        )
        self.client.force_login(u)
        from plugins.registry import plugin_registry

        self._adm = plugin_registry.get('admin_dashboard')
        self._adm.set_config('setup_guide_dismissed', False)
        self._adm.invalidate_config_cache()

    def test_widget_shows_then_hides_after_skip_and_persists(self):
        # Fresh store (no products/orders/keys) → checklist is visible.
        html = self.client.get('/dashboard/').content.decode()
        self.assertIn('Set up your store', html)
        self.assertIn('/dashboard/setup/dismiss/', html)  # the Skip form

        # Skip it.
        resp = self.client.post('/dashboard/setup/dismiss/')
        self.assertEqual(resp.status_code, 302)
        self._adm.invalidate_config_cache()
        self.assertTrue(self._adm.get_config_value('setup_guide_dismissed', False))

        # Gone now — and stays gone on the next load (persisted server-side).
        html2 = self.client.get('/dashboard/').content.decode()
        self.assertNotIn('Set up your store', html2)

    def test_dismiss_requires_post(self):
        # A GET must not mutate state (CSRF-safe).
        self.client.get('/dashboard/setup/dismiss/')
        self._adm.invalidate_config_cache()
        self.assertFalse(self._adm.get_config_value('setup_guide_dismissed', False))


class RecentOrdersEmailCellTests(TestCase):
    """Regression: the recent-orders email cell must not 500 on a guest order
    (no customer + empty email). `default:o.customer.email` resolved the arg
    eagerly → None.email → VariableDoesNotExist (filter args aren't swallowed).
    firstof swallows the failed lookup."""

    def test_guest_order_no_customer_renders_dash(self):
        from django.template import Context, Template

        t = Template("{% firstof o.email o.customer.email '—' %}")

        class _Guest:
            email = ''
            customer = None

        class _Cust:
            email = 'c@x.test'

        class _WithCust:
            email = ''
            customer = _Cust()

        self.assertEqual(t.render(Context({'o': _Guest()})), '—')  # the 500 case
        self.assertEqual(t.render(Context({'o': _WithCust()})), 'c@x.test')
