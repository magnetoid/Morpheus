"""Phase 4: static safety scan + code-proposal drafting (self-written modules).

These never execute candidate source — pure AST analysis + a DB proposal row."""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from core.assistant.codegen import passed, scan_source
from core.assistant.models import CodeProposal
from core.assistant.tools.code import code_draft_tool, code_list_proposals_tool

_GOOD = (
    'from core.assistant.tools.filesystem import ToolResult, tool\n'
    "@tool(name='x.ping', description='ping', scopes=['system.read'], schema={'type':'object','properties':{}})\n"
    'def x_ping_tool():\n'
    "    return ToolResult(output={'ok': True})\n"
)


def _codes(findings):
    return {f['code'] for f in findings}


class ScanSourceTests(SimpleTestCase):
    def test_clean_tool_passes(self):
        findings = scan_source(_GOOD, kind='tool')
        self.assertTrue(passed(findings), findings)

    def test_syntax_error_critical(self):
        f = scan_source('def (:', kind='tool')
        self.assertIn('syntax', _codes(f))
        self.assertFalse(passed(f))

    def test_flags_dangerous_calls(self):
        self.assertIn('danger_call', _codes(scan_source('result = eval("1")')))
        self.assertIn('danger_call', _codes(scan_source('import os\nos.system("rm -rf /")')))

    def test_flags_hallucinated_import(self):
        f = scan_source('import totally_not_a_real_pkg_xyz\n')
        self.assertIn('unknown_import', _codes(f))
        self.assertFalse(passed(f))

    def test_known_imports_ok(self):
        f = scan_source('import json\nimport os\nfrom core.agents.tools import Tool\n' + _GOOD)
        self.assertNotIn('unknown_import', _codes(f))

    def test_sql_fstring_flagged(self):
        f = scan_source('def r(c, x):\n    return c.execute(f"SELECT {x}")\n')
        self.assertIn('sql_fstring', _codes(f))

    def test_missing_tool_shape(self):
        f = scan_source('def helper():\n    return 1\n', kind='tool')
        self.assertIn('no_tool', _codes(f))


class DraftToolTests(TestCase):
    def test_draft_persists_proposal(self):
        res = code_draft_tool.invoke(
            {'name': 'Low Stock Report', 'source': _GOOD, 'rationale': 'need it'}
        )
        self.assertTrue(res.output['passed'])
        self.assertEqual(res.output['status'], 'draft')
        p = CodeProposal.objects.get(name='low-stock-report')
        self.assertEqual(p.status, 'draft')  # never auto-applied
        self.assertTrue(p.passed)

    def test_draft_records_blocking_findings(self):
        res = code_draft_tool.invoke({'name': 'bad', 'source': 'import nope_pkg_xyz\n'})
        self.assertFalse(res.output['passed'])
        self.assertTrue(any(f['severity'] == 'HIGH' for f in res.output['findings']))

    def test_list_proposals(self):
        code_draft_tool.invoke({'name': 'a', 'source': _GOOD})
        out = code_list_proposals_tool.invoke({}).output
        self.assertGreaterEqual(out['count'], 1)
        self.assertIn('a', [p['name'] for p in out['proposals']])


class ShapeEvalTests(SimpleTestCase):
    _DECL = 'from core.assistant.tools.filesystem import ToolResult, tool\n'

    def test_signature_schema_mismatch(self):
        src = self._DECL + (
            "@tool(name='y.t', description='d', schema={'type':'object','properties':{}})\n"
            'def y_t(*, foo):\n'
            '    return ToolResult(output={})\n'
        )
        self.assertIn('sig_mismatch', _codes(scan_source(src)))

    def test_param_in_schema_ok(self):
        src = self._DECL + (
            "@tool(name='y.t', description='d', schema={'type':'object','properties':{'foo':{}}})\n"
            'def y_t(*, foo):\n'
            '    return ToolResult(output={})\n'
        )
        self.assertNotIn('sig_mismatch', _codes(scan_source(src)))

    def test_missing_toolresult_return(self):
        src = self._DECL + (
            "@tool(name='z.t', description='d', schema={'type':'object','properties':{}})\n"
            'def z_t():\n'
            '    return 5\n'
        )
        self.assertIn('no_toolresult', _codes(scan_source(src)))

    def test_runtime_kwargs_not_flagged(self):
        # agent/context are runtime-injected, not schema properties.
        src = self._DECL + (
            "@tool(name='r.t', description='d', schema={'type':'object','properties':{}})\n"
            'def r_t(*, agent=None, context=None):\n'
            '    return ToolResult(output={})\n'
        )
        self.assertNotIn('sig_mismatch', _codes(scan_source(src)))
