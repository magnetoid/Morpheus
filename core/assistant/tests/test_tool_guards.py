"""Agent tool-surface guards (core audit S6 / S8 / S4).

These block three ways an injected/over-broad agent turn could do damage:
secret exfiltration via fs.read_file, soft-bricking via plugins.disable, and an
un-throttled OTP-issuance email relay.
"""

from __future__ import annotations

import re

from django.test import SimpleTestCase

from core.agents import ToolError
from core.assistant.tools.filesystem import read_file_tool
from core.assistant.tools.plugins import disable_plugin_tool


class ReadFileGuardTests(SimpleTestCase):
    def test_env_file_refused(self):
        # S6: .env is in PROTECTED_PATHS — reading it would land secrets in
        # AgentStep rows + transcripts.
        with self.assertRaises(ToolError) as cm:
            read_file_tool.invoke({'path': '.env'})
        self.assertIn('protected', str(cm.exception).lower())

    def test_key_material_refused(self):
        with self.assertRaises(ToolError):
            read_file_tool.invoke({'path': 'secrets/id_rsa'})
        with self.assertRaises(ToolError):
            read_file_tool.invoke({'path': 'plugins/installed/payments/services.py'})

    def test_dotdot_evasion_refused(self):
        # _safe_path resolves before the protected check, so ../ can't dodge it.
        with self.assertRaises(ToolError):
            read_file_tool.invoke({'path': 'core/../.env'})

    def test_ordinary_file_still_reads(self):
        out = read_file_tool.invoke({'path': 'docs/RELEASE_NOTES.md'}).output
        self.assertIn('content', out)


class DisablePluginGuardTests(SimpleTestCase):
    def test_protected_plugin_refused(self):
        # S8: disabling admin_dashboard/orders/rbac/… soft-bricks the platform.
        # Refused before the hard-gate even prompts.
        for name in ('admin_dashboard', 'agent_core', 'rbac', 'customers'):
            with self.assertRaises(ToolError) as cm:
                disable_plugin_tool.invoke({'name': name})
            self.assertIn('protected', str(cm.exception).lower())


class OtpRateRuleTests(SimpleTestCase):
    def test_otp_paths_are_throttled(self):
        # S4: the auth rate rule must cover the mounted /auth/otp/ issuance path.
        from core.ratelimit import _RULES

        auth_rule = next((p for p, bucket, _ in _RULES if bucket == 'auth'), None)
        self.assertIsNotNone(auth_rule)
        self.assertTrue(auth_rule.match('/auth/otp/'))
        self.assertTrue(auth_rule.match('/auth/otp/verify/'))
        # still covers the original entry points
        self.assertTrue(auth_rule.match('/auth/login/'))
        # and doesn't over-match unrelated paths
        self.assertFalse(auth_rule.match('/auth/profile/'))
        self.assertIsInstance(auth_rule, re.Pattern)
