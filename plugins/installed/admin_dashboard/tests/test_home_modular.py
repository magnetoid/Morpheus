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


def _function_body(src: str, name: str) -> str:
    start = src.index(f'def {name}')
    end = src.find('\ndef ', start + 1)
    return src[start:] if end == -1 else src[start:end]


class DashboardHomeModularityTests(TestCase):
    def test_home_assembly_no_longer_imports_sibling_plugin_models(self):
        # Scope to dashboard_home + _compute_setup_steps — pulse_refresh /
        # pulse_dismiss are whole ai_assistant-owned routes and migrate in a
        # separate increment (see the plan doc).
        src = _HOME_PY.read_text(encoding='utf-8')
        for fn in ('dashboard_home', '_compute_setup_steps'):
            body = _function_body(src, fn)
            for plugin in ('orders', 'catalog', 'ai_assistant', 'agent_core', 'inventory'):
                self.assertNotIn(
                    f'installed.{plugin}',
                    body,
                    f'{fn} still imports {plugin} — it belongs in that '
                    "plugin's dashboard filter subscriber",
                )

    def test_contributing_plugins_are_subscribed(self):
        from core.hooks import MorpheusEvents, hook_registry

        def quals(event):
            return {
                getattr(h, '__qualname__', '')
                for (_prio, h, _mode) in hook_registry._handlers.get(event, [])
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

        from core.hooks import MorpheusEvents, hook_registry
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
