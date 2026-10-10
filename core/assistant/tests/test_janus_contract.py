"""The Janus contract stays in step with what Morpheus actually relies on.

core/assistant/janus_contract.py runs inside a Janus install (the build, the
auto-updater, the Janus page) and cannot import Morpheus, so its expectations are
a copy. These tests are what keeps the copy honest: a toolset, config key, CLI
option or env var Morpheus starts to use must be in the contract too, or a Janus
that drops it would be adopted without anyone noticing.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import SimpleTestCase

from core.assistant import janus_contract as contract
from core.assistant import janus_engine as eng

# Config keys the contract need not prove: names Morpheus chooses itself
# (the MCP server and its connection) and values with no behaviour to lose.
_NOT_PROVED = {
    'model.default',  # 'auto' unless JANUS_INFERENCE_MODEL; the turn pins -m anyway
    'mcp_servers.*.url',
    'mcp_servers.*.headers',
    'mcp_servers.*.timeout',
    'mcp_servers.*.tools.resources',
    'mcp_servers.*.tools.prompts',
    'hooks.pre_tool_call',
    'hooks.post_tool_call',
}


def _config_keys(text: str) -> set[str]:
    """Dotted keys of the generated YAML: the MCP server name as ``*``, a hook as its event."""
    keys, path = set(), []
    for line in text.splitlines():
        m = re.match(r'^( *)([A-Za-z_][\w-]*):\s*(.*)$', line)
        if not m:
            continue  # comments, list items, blank lines
        depth = len(m.group(1)) // 2
        path = [*path[:depth], m.group(2)]
        parts = list(path)
        if parts[0] == 'mcp_servers' and len(parts) > 1:
            parts[1] = '*'
            parts = parts[:4] if parts[2:3] == ['tools'] else parts[:3]
        if parts[0] == 'hooks':
            parts = parts[:2]
        if parts[0] == 'fallback_providers':  # a list of {provider, model}: one key
            parts = parts[:1]
        special = parts[0] == 'hooks' or parts[-1] in (
            'external_dirs',
            'headers',
            'fallback_providers',
        )
        if m.group(3).strip() or special:
            keys.add('.'.join(parts))
    return keys - {'hooks', 'mcp_servers.*'}


class ContractInStepTests(SimpleTestCase):
    def test_every_toolset_a_turn_can_load_is_in_the_contract(self):
        loadable = set(eng.TURN_TOOLSETS + eng.WEB_SEARCH_TOOLSETS + eng.LEARNING_TOOLSETS)
        self.assertEqual(set(contract.TOOLSETS), loadable - {eng.MCP_SERVER_NAME})

    def test_every_config_key_morpheus_writes_is_proved_or_waived(self):
        # With a backup provider configured, so `fallback_providers` is written too.
        text = eng._config_text(
            'https://s/mcp/',
            {'Host': 'x'},
            Path('/tmp/p.jsonl'),
            fallbacks=[{'provider': 'deepseek', 'model': 'deepseek-chat'}],
        )
        written = _config_keys(text)
        self.assertIn('skills.inline_shell', written)  # the parser works
        unproved = written - set(contract.CONFIG_KEYS) - _NOT_PROVED
        self.assertEqual(unproved, set(), 'add each to CONFIG_KEYS with a source pattern')
        self.assertEqual(
            set(contract.CONFIG_KEYS) - written, set(), 'the contract checks a key nobody writes'
        )

    def test_the_env_vars_a_turn_sets_are_in_the_contract(self):
        with TemporaryDirectory() as tmp:
            env = eng._turn_env(Path(tmp), 'prompt', 'token', {})
        for name in ('JANUS_HOME', 'JANUS_EPHEMERAL_SYSTEM_PROMPT', 'JANUS_YOLO_MODE'):
            self.assertIn(name, env)
            self.assertIn(f'env {name}', contract.NAMES)

    def test_every_chat_option_a_turn_passes_is_in_the_contract(self):
        with (
            TemporaryDirectory() as tmp,
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(eng, 'linda_janus_home', return_value=Path(tmp)),
            mock.patch.object(
                eng, '_provider_wiring', return_value=(['--provider', 'x', '-m', 'y'], {})
            ),
            mock.patch.object(
                eng.subprocess,
                'run',
                return_value=subprocess.CompletedProcess([], 0, 'ok', 'session_id: s1'),
            ),
        ):
            eng.run_janus_turn(message='hi', conversation_key='c', system_prompt='p')
            with mock.patch.object(
                eng.subprocess,
                'run',
                return_value=subprocess.CompletedProcess([], 0, 'ok', 'session_id: s1'),
            ) as spawn:
                eng.run_janus_turn(message='hi again', conversation_key='c', system_prompt='p')
        argv = spawn.call_args.args[0]
        used = {a for a in argv if a.startswith('-')}
        self.assertEqual(used - set(contract.CHAT_FLAGS), set())

    def test_the_notices_stripped_from_answers_are_watched(self):
        for prefix in eng._NOTICE_PREFIXES:
            words = prefix.split(None, 1)[1].strip()
            self.assertTrue(any(words in key for key in contract.SOFT_NAMES), prefix)


def _fake_janus(root: Path, *, search_tools=('web_search',), drop: str = '') -> Path:
    """A minimal Janus tree with just what the contract reads."""
    toolsets = dict.fromkeys(contract.TOOLSETS)
    for name, tools in contract.TOOLSETS.items():
        toolsets[name] = {'tools': sorted(tools), 'includes': []}
    toolsets['search'] = {'tools': list(search_tools), 'includes': []}
    (root / 'toolsets.py').write_text(f'TOOLSETS = {toolsets!r}\n', encoding='utf-8')
    needles = [
        'tirith_enabled max_turns reasoning_effort api_max_retries supports_parallel_tool_calls',
        'guard_agent_created inline_shell creation_nudge_interval external_dirs',
        'memory_enabled user_profile_enabled cfg.nudge_interval hooks_auto_accept',
        'fallback_providers',
        'cfg.get("curator") web.get("backend")',
        'JANUS_HOME JANUS_EPHEMERAL_SYSTEM_PROMPT JANUS_YOLO_MODE SOUL.md .no-bundled-skills',
        'print(f"\\nsession_id: {cli.session_id}", file=sys.stderr)',
        'Session not found',
        'Reached maximum iterations All API retries exhausted',
    ]
    body = '\n'.join(f'# {n}' for n in needles)
    if drop:
        body = body.replace(drop, 'gone')
    (root / 'cli.py').write_text(body + '\n', encoding='utf-8')
    (root / 'janus_state.py').write_text(
        textwrap.dedent(
            """
            SCHEMA = '''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                model TEXT,
                parent_session_id TEXT,
                started_at REAL NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_write_tokens INTEGER DEFAULT 0,
                reasoning_tokens INTEGER DEFAULT 0,
                estimated_cost_usd REAL,
                api_call_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                timestamp REAL NOT NULL
            );
            '''
            """
        ),
        encoding='utf-8',
    )
    for package, init in (
        ('agent', ''),
        ('tools', ''),
        ('janus_cli', ''),
        ('mcp', ''),
        ('ddgs', ''),
    ):
        (root / package).mkdir()
        (root / package / '__init__.py').write_text(init, encoding='utf-8')
    (root / 'janus_cli' / 'plugins.py').write_text(
        "VALID_HOOKS = {'pre_tool_call', 'post_tool_call'}\n", encoding='utf-8'
    )
    (root / 'agent' / 'shell_hooks.py').write_text(
        'class _S:\n    def __init__(self, e):\n        self.event = e\n'
        "def iter_configured_hooks(cfg):\n    return [_S(e) for e in (cfg.get('hooks') or {})]\n",
        encoding='utf-8',
    )
    janus = root / 'janus'
    janus.write_text(
        '#!/bin/sh\necho "usage: janus chat [-q QUERY] [-Q] [-t TOOLSETS] [--resume ID]'
        ' [--source SOURCE] [--provider P] [-m MODEL]"\n',
        encoding='utf-8',
    )
    janus.chmod(0o755)
    return janus


class ContractScriptTests(SimpleTestCase):
    """The script itself, run the way the build and the updater run it."""

    def _run(self, **fake) -> dict:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            janus = _fake_janus(root, **fake)
            env = {'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(root)}
            proc = subprocess.run(  # noqa: S603
                [sys.executable, str(Path(contract.__file__)), '--janus', str(janus)],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
                check=False,
            )
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0 if report['ok'] else 1)
        return report

    @staticmethod
    def _failing(report):
        return sorted(c['name'] for c in report['checks'] if c['required'] and not c['ok'])

    def test_a_compatible_janus_passes(self):
        report = self._run()
        self.assertEqual(self._failing(report), [])
        self.assertTrue(report['ok'])

    def test_a_toolset_that_grows_a_tool_fails(self):
        # Upstream adding page fetching to `search` must not reach Linda unreviewed.
        report = self._run(search_tools=('web_search', 'web_extract'))
        self.assertEqual(self._failing(report), ['toolset search'])

    def test_a_config_key_nothing_reads_any_more_fails(self):
        report = self._run(drop='inline_shell')
        self.assertEqual(self._failing(report), ['config skills.inline_shell'])

    def test_a_renamed_system_prompt_variable_fails(self):
        report = self._run(drop='JANUS_EPHEMERAL_SYSTEM_PROMPT')
        self.assertEqual(self._failing(report), ['env JANUS_EPHEMERAL_SYSTEM_PROMPT'])

    def test_it_imports_nothing_from_morpheus(self):
        source = Path(contract.__file__).read_text(encoding='utf-8')
        self.assertNotRegex(source, r'^\s*(from|import) (django|core|plugins)\b')
