"""Core agent sandbox + run_python bridge safety (uplift Phase 2)."""

from __future__ import annotations

from django.test import SimpleTestCase

from core.agents.sandbox import SandboxError, run_sandboxed
from core.agents.tools import Tool, ToolError, ToolResult
from core.assistant.tools.code import run_python_tool


class SandboxTests(SimpleTestCase):
    def test_returns_result_variable(self):
        self.assertEqual(run_sandboxed('result = 1 + 2'), 3)

    def test_blocks_import(self):
        with self.assertRaises(SandboxError):
            run_sandboxed('import os\nresult = 1')

    def test_blocks_dunder_access(self):
        with self.assertRaises(SandboxError):
            run_sandboxed('result = ().__class__')

    def test_blocks_open_and_eval_names(self):
        with self.assertRaises(SandboxError):
            run_sandboxed('result = open("/etc/passwd")')
        with self.assertRaises(SandboxError):
            run_sandboxed('result = eval("1")')

    def test_timeout(self):
        with self.assertRaises(SandboxError):
            run_sandboxed('\nx = 0\nwhile True:\n    x += 1\nresult = x', timeout_ms=120)

    def test_in_script_error_is_wrapped(self):
        with self.assertRaises(SandboxError):
            run_sandboxed('result = 1 / 0')

    def test_extra_globals_bridge(self):
        out = run_sandboxed('result = call(2, 3)', extra_globals={'call': lambda a, b: a + b})
        self.assertEqual(out, 5)


def _tool(name, *, requires_approval=False, scopes=None, output='ok'):
    return Tool(
        name=name,
        description=name,
        handler=lambda **kw: ToolResult(output={'echo': kw, 'name': name, 'fixed': output}),
        schema={'type': 'object', 'properties': {}},
        scopes=scopes or [],
        requires_approval=requires_approval,
    )


class _StubAgent:
    def __init__(self, tools, scopes=None):
        self._tools = tools
        self.scopes = scopes or []

    def get_tools(self):
        return self._tools


class RunPythonBridgeTests(SimpleTestCase):
    def _run(self, code, tools, agent_scopes=None):
        return run_python_tool.invoke({'code': code}, agent=_StubAgent(tools, scopes=agent_scopes))

    def test_call_invokes_read_tool(self):
        res = self._run('result = call("db.list_models")', [_tool('db.list_models')])
        self.assertEqual(res.output['result']['name'], 'db.list_models')
        self.assertEqual(res.output['call_count'], 1)

    def test_approval_gated_tool_not_callable(self):
        # An approval-required (write) tool must NOT be reachable from a script.
        with self.assertRaises(ToolError):
            self._run(
                'result = call("orders.cancel")', [_tool('orders.cancel', requires_approval=True)]
            )

    def test_unknown_tool_rejected(self):
        with self.assertRaises(ToolError):
            self._run('result = call("nope.nope")', [_tool('safe.read')])

    def test_write_scoped_tool_not_callable(self):
        # Non-approval but write-scoped (e.g. delegate.spawn_workers) is excluded.
        with self.assertRaises(ToolError):
            self._run(
                'result = call("delegate.spawn_workers")',
                [_tool('delegate.spawn_workers', scopes=['system.write'])],
            )

    def test_scope_enforced_in_bridge(self):
        # A read tool the agent lacks scope for must be refused (Tool.invoke does
        # not check scopes; the bridge must).
        with self.assertRaises(ToolError):
            self._run(
                'result = call("orders.read")',
                [_tool('orders.read', scopes=['orders.read'])],
                agent_scopes=[],  # agent has NO scopes
            )

    def test_call_cap_enforced(self):
        code = 'for _ in range(100):\n    call("safe.read")\nresult = "done"'
        with self.assertRaises(ToolError):
            self._run(code, [_tool('safe.read')])

    def test_composes_multiple_calls(self):
        code = 'rows = call("a.read")\nmore = call("b.read")\nresult = [rows["name"], more["name"]]'
        res = self._run(code, [_tool('a.read'), _tool('b.read')])
        self.assertEqual(res.output['result'], ['a.read', 'b.read'])
        self.assertEqual(res.output['call_count'], 2)
