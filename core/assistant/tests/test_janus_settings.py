"""Janus dashboard settings — overlay + Linda-branded page (no DB)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.assistant.janus_config import resolved_auto_approve, resolved_engine, resolved_timeout_s
from core.assistant.views_settings import JanusDashboardForm, assistant_settings
from plugins.installed.admin_dashboard.forms.settings import StoreGeneralForm


class JanusConfigResolveTests(SimpleTestCase):
    @override_settings(LINDA_ENGINE='legacy')
    @patch('core.assistant.janus_config._row')
    def test_process_legacy_pin_wins(self, mock_row):
        mock_row.return_value = SimpleNamespace(engine='janus', pk=1)
        self.assertEqual(resolved_engine(), 'legacy')

    @override_settings(LINDA_ENGINE='janus')
    @patch('core.assistant.janus_config._row')
    def test_dashboard_engine_overlay(self, mock_row):
        mock_row.return_value = SimpleNamespace(engine='legacy', pk=1)
        self.assertEqual(resolved_engine(), 'legacy')

    @override_settings(LINDA_ENGINE='janus', LINDA_JANUS_AUTO_APPROVE=False)
    @patch('core.assistant.janus_config._row')
    def test_dashboard_auto_approve_overlay(self, mock_row):
        mock_row.return_value = SimpleNamespace(auto_approve=True, pk=1)
        self.assertTrue(resolved_auto_approve())

    @override_settings(LINDA_ENGINE='janus', LINDA_JANUS_TIMEOUT_S=55)
    @patch('core.assistant.janus_config._row')
    def test_dashboard_timeout_is_capped(self, mock_row):
        mock_row.return_value = SimpleNamespace(timeout_s=90, pk=1)
        self.assertEqual(resolved_timeout_s(), 55)

    @override_settings(LINDA_ENGINE='janus', LINDA_JANUS_AUTO_APPROVE=True)
    @patch('core.assistant.janus_config._row')
    def test_unsaved_row_uses_django(self, mock_row):
        mock_row.return_value = SimpleNamespace(auto_approve=False, pk=None)
        self.assertTrue(resolved_auto_approve())


class JanusDashboardFormTests(SimpleTestCase):
    def test_apply_keeps_blank_token(self):
        form = JanusDashboardForm(
            data={
                'engine': 'janus',
                'model': 'grok-4',
                'timeout_s': '40',
                'mcp_url': 'https://shop.example/mcp/admin/v1',
                'mcp_token': '',
                'auto_approve': 'on',
                'ai_daily_briefing': 'on',
                'ai_page_help': 'on',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        row = SimpleNamespace(
            pk=1,
            engine='',
            model='',
            auto_approve=False,
            timeout_s=None,
            mcp_url='',
            mcp_token='keep-me',
            save=MagicMock(),
        )
        store = SimpleNamespace(ai_page_help=False, ai_daily_briefing=False, save=MagicMock())
        form.apply(row, store)
        self.assertEqual(row.engine, 'janus')
        self.assertEqual(row.model, 'grok-4')
        self.assertEqual(row.timeout_s, 40)
        self.assertTrue(row.auto_approve)
        self.assertEqual(row.mcp_token, 'keep-me')
        self.assertTrue(store.ai_daily_briefing)
        self.assertTrue(store.ai_page_help)
        row.save.assert_called_once()
        store.save.assert_called_once()


class JanusSettingsPageTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.user = SimpleNamespace(
            is_active=True, is_staff=True, is_authenticated=True, pk=1, is_anonymous=False
        )

    def test_anonymous_redirects(self):
        req = self.rf.get('/dashboard/assistant/settings/')
        req.user = AnonymousUser()
        resp = assistant_settings(req)
        self.assertEqual(resp.status_code, 302)

    @patch('core.assistant.views_settings.render', return_value=HttpResponse('Linda Janus Daily briefing'))
    @patch('core.assistant.janus_config.status_snapshot', return_value={'engine': 'legacy', 'skills': []})
    @patch('core.models.StoreSettings.objects')
    @patch('core.assistant.models.JanusSettings.load')
    def test_staff_get_ok(self, mock_load, mock_store_objects, _status, mock_render):
        mock_load.return_value = SimpleNamespace(
            engine='', model='', timeout_s=None, mcp_url='', mcp_token='', auto_approve=False, pk=None
        )
        mock_store_objects.first.return_value = SimpleNamespace(
            store_name='Shop', ai_page_help=False, ai_daily_briefing=False, pk=1
        )
        req = self.rf.get('/dashboard/assistant/settings/')
        req.user = self.user
        resp = assistant_settings(req)
        self.assertEqual(resp.status_code, 200)
        mock_render.assert_called_once()
        ctx = mock_render.call_args[0][2]
        self.assertIn('status', ctx)
        self.assertEqual(ctx['active_nav'], 'assistant')


class StoreGeneralNoLongerOwnsLindaTogglesTests(SimpleTestCase):
    def test_form_has_no_linda_toggles(self):
        self.assertNotIn('ai_page_help', StoreGeneralForm.base_fields)
        self.assertNotIn('ai_daily_briefing', StoreGeneralForm.base_fields)
