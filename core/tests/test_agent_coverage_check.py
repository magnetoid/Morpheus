"""scripts/check_agent_coverage.py: every staff write view has Linda's tool, or says why not.

The script is the ADR 0039 ratchet (P8, v0.182.0). These tests run it on the real
tree (it must agree with its baseline, so the suite catches what CI would) and on
small made-up trees, so a guard that quietly stopped finding views fails here.
"""

from __future__ import annotations

import importlib.util
import tempfile
import textwrap
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

_SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'check_agent_coverage.py'


def _load():
    spec = importlib.util.spec_from_file_location('check_agent_coverage', _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RealTreeTests(SimpleTestCase):
    def test_the_tree_matches_its_baseline_and_every_map_is_valid(self):
        check = _load()
        uncovered, errors, covered = check.scan()
        self.assertEqual(errors, [])
        self.assertEqual(set(uncovered), check._load_baseline())
        self.assertGreater(covered, 0)

    def test_the_settings_panel_and_the_order_forms_are_covered(self):
        uncovered, _errors, _covered = _load().scan()
        for view in (
            'plugins.installed.admin_dashboard.urls:plugin_settings_view',
            'plugins.installed.admin_dashboard.views_split.orders:order_refund',
            'plugins.installed.admin_dashboard.views_split.orders:order_fulfill',
        ):
            self.assertNotIn(view, uncovered)


_TOOLS = """
from core.agents.tools import tool

@tool(name='demo.save', description='x')
def save_tool():
    pass
"""

_VIEWS = """
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST

{map}

@staff_member_required
def edit(request):
    if request.method == 'POST':
        return None

@staff_member_required
@require_POST
def remove(request):
    return None

@staff_member_required
def read_only(request):
    return None

def public_form(request):
    return request.POST.get('x')

def page_view(request):
    return request.POST
"""

_APP = """
from plugins.contributions import DashboardPage

PAGE = DashboardPage(label='x', slug='x', view='plugins.installed.demo.views.page_view')
"""


class MadeUpTreeTests(SimpleTestCase):
    def _scan(self, agent_map: str = ''):
        check = _load()
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / 'plugins' / 'installed' / 'demo'
            app.mkdir(parents=True)
            (app / 'agent_tools.py').write_text(_TOOLS)
            (app / 'views.py').write_text(_VIEWS.format(map=textwrap.dedent(agent_map)))
            (app / 'app.py').write_text(_APP)
            (Path(tmp) / 'core').mkdir()
            (Path(tmp) / 'api').mkdir()
            with mock.patch.object(check, 'REPO_ROOT', Path(tmp)):
                return check.scan()

    def test_staff_views_that_accept_post_are_found(self):
        uncovered, errors, _covered = self._scan()
        self.assertEqual(errors, [])
        self.assertEqual(
            uncovered,
            [
                'plugins.installed.demo.views:edit',
                'plugins.installed.demo.views:page_view',  # served to staff by the router
                'plugins.installed.demo.views:remove',
            ],
        )

    def test_a_tool_or_a_reason_covers_a_view(self):
        uncovered, errors, covered = self._scan(
            "AGENT_TOOLS = {'edit': 'demo.save', 'remove': 'none: deleting this stays a human call'}"
        )
        self.assertEqual(errors, [])
        self.assertEqual(uncovered, ['plugins.installed.demo.views:page_view'])
        self.assertEqual(covered, 2)

    def test_a_tool_no_app_registers_is_an_error(self):
        _uncovered, errors, _covered = self._scan("AGENT_TOOLS = {'edit': 'demo.missing'}")
        self.assertEqual(len(errors), 1)
        self.assertIn('no app registers', errors[0])

    def test_none_needs_a_reason(self):
        _uncovered, errors, _covered = self._scan("AGENT_TOOLS = {'edit': 'none:'}")
        self.assertIn('without a reason', errors[0])

    def test_an_entry_for_a_view_that_writes_nothing_is_an_error(self):
        _uncovered, errors, _covered = self._scan("AGENT_TOOLS = {'read_only': 'demo.save'}")
        self.assertIn('names no staff view', errors[0])

    def test_a_map_that_is_not_a_literal_is_an_error(self):
        _uncovered, errors, _covered = self._scan("AGENT_TOOLS = dict(edit='demo.save')")
        self.assertIn('literal dict', errors[0])

    def test_the_baseline_only_shrinks(self):
        check = _load()
        with (
            mock.patch.object(check, 'scan', return_value=(['a:b'], [], 0)),
            mock.patch.object(check, '_load_baseline', return_value={'a:b', 'a:gone'}),
            mock.patch('builtins.print'),
        ):
            self.assertEqual(check.main([]), 1)
        with (
            mock.patch.object(check, 'scan', return_value=(['a:b', 'a:new'], [], 0)),
            mock.patch.object(check, '_load_baseline', return_value={'a:b'}),
            mock.patch('builtins.print'),
        ):
            self.assertEqual(check.main([]), 1)
        with (
            mock.patch.object(check, 'scan', return_value=(['a:b'], [], 0)),
            mock.patch.object(check, '_load_baseline', return_value={'a:b'}),
            mock.patch('builtins.print'),
        ):
            self.assertEqual(check.main([]), 0)
