"""Fix 5 — the staged approval-gate exemption is scoped to staging tools.

Regression for the S1 / hunt #5 hole: `context['staged']` used to exempt
*every* requires_approval tool from the approval gate. A tool WITHOUT a staging
path (`supports_staging=False`) then hard-executed with zero approval under
staged context — staged=True → skip approval → the tool has no staged branch →
it writes directly. The exemption is now scoped to `tool.supports_staging=True`
(those record an OpsProposal for human review — the proposal IS the sign-off).

Reuses `_agent` / `_tool` from `test_runtime`; a `supports_staging=True` tool
is built with `Tool(...)` directly (the `_tool` helper never sets that flag).
"""

from __future__ import annotations

from django.test import TestCase

from core.agents.llm import LLMResponse, LLMToolCall, MockLLMProvider
from core.agents.runtime import AgentRuntime
from core.agents.tests.test_runtime import _agent, _tool
from core.agents.tools import Tool


def _single_dispatch_provider() -> MockLLMProvider:
    """One tool call to `do_thing`, then a final answer — a single dispatch."""
    return MockLLMProvider(
        [
            LLMResponse(tool_calls=[LLMToolCall(id='c1', name='do_thing', arguments={})]),
            LLMResponse(text='done'),
        ]
    )


def _staging_tool(*, handler) -> Tool:
    """A requires_approval tool that ALSO implements staging (the _tool helper
    can't set supports_staging, so build the Tool directly)."""
    return Tool(
        name='do_thing',
        description='d',
        handler=handler,
        requires_approval=True,
        supports_staging=True,
    )


class StagedApprovalGateScopeTests(TestCase):
    def _run(self, tool, *, context=None):
        agent = _agent(tools=[tool])
        return AgentRuntime(agent, provider=_single_dispatch_provider()).run(
            user_message='go', context=context
        )

    def test_non_staging_tool_still_gated_under_staged_context(self):
        # supports_staging defaults to False on `_tool(...)`. Staged context must
        # NOT exempt it — the gate fires and the handler never runs (the S1 hole
        # would have executed it unapproved).
        called = []
        tool = _tool(requires_approval=True, handler=lambda **kw: called.append(1))
        self.assertFalse(tool.supports_staging)  # guard: exemption must not apply

        res = self._run(tool, context={'staged': True})

        self.assertEqual(called, [])  # gate fired — handler did not write
        approval_steps = [s for s in res.trace.steps if s.metadata.get('approval_required')]
        self.assertTrue(approval_steps)  # STEP_APPROVAL_REQUIRED recorded
        failed = [s for s in res.trace.steps if s.metadata.get('failed')]
        self.assertTrue(any(s.content == 'approval_required' for s in failed))

    def test_staging_tool_exempt_under_staged_context(self):
        # A supports_staging=True tool records its own proposal, so the token
        # gate is exempt under staged context — the handler runs.
        called = []
        tool = _staging_tool(handler=lambda **kw: called.append(1) or {'ok': True})

        res = self._run(tool, context={'staged': True})

        self.assertEqual(called, [1])  # exempt — handler ran
        self.assertEqual(res.state, 'completed')

    def test_staging_tool_still_gated_without_staged_context(self):
        # The exemption requires staged context. The SAME staging tool run as a
        # DIRECT write (no staged context, no approval_check) is still gated by
        # the fail-closed registry.
        called = []
        tool = _staging_tool(handler=lambda **kw: called.append(1) or {'ok': True})

        res = self._run(tool)  # no staged context

        self.assertEqual(called, [])  # gate fired
        approval_steps = [s for s in res.trace.steps if s.metadata.get('approval_required')]
        self.assertTrue(approval_steps)
