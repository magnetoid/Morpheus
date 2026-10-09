"""Morpheus's contract with Janus: everything Linda's integration relies on.

Run it with the Python of the Janus install being checked::

    /opt/janus/bin/python -I core/assistant/janus_contract.py

It imports that install's modules and reads its source, prints a JSON report and
exits 1 when a required check fails. Three callers:

* the Docker build, which falls back to the last known-good Janus when ``main``
  fails it, so an image never ships an incompatible engine;
* the auto-updater (core/assistant/janus_updater.py), which installs a newer
  Janus beside the current one and switches Linda to it only when it passes;
* the Janus settings page, which shows the report for the Janus in use.

Standard library only, and no Morpheus imports: it runs inside Janus's venv.
Every expectation mirrors core/assistant/janus_engine.py, and
core/assistant/tests/test_janus_contract.py keeps the two in step.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Toolsets a turn may load, and the only tools each may hold. These are the
# tools reviewed for the boundary in janus_engine.py: a toolset that grows a
# tool upstream fails the contract instead of reaching Linda unreviewed.
TOOLSETS = {
    'skills': {'skills_list', 'skill_view', 'skill_manage'},
    'todo': {'todo'},
    'session_search': {'session_search'},
    'search': {'web_search'},
    'memory': {
        'memory',
        'recall_memory',
        'recall_lessons',
        'pin_agreement',
        'recall_agreements',
        'propose_plan',
    },
}

# Config keys janus_engine writes, each with a pattern Janus's source must still
# contain, as proof that something reads the key. A key nothing reads is a
# setting silently ignored, and several of these are safety settings.
CONFIG_KEYS = {
    'security.tirith_enabled': r'tirith_enabled',
    'agent.max_turns': r'max_turns',
    'agent.reasoning_effort': r'reasoning_effort',
    'agent.api_max_retries': r'api_max_retries',
    'mcp_servers.*.supports_parallel_tool_calls': r'supports_parallel_tool_calls',
    'skills.guard_agent_created': r'guard_agent_created',
    'skills.inline_shell': r'inline_shell',
    'skills.creation_nudge_interval': r'creation_nudge_interval',
    'skills.external_dirs': r'external_dirs',
    'curator.enabled': r'get\(\s*["\']curator["\']',
    'memory.memory_enabled': r'memory_enabled',
    'memory.user_profile_enabled': r'user_profile_enabled',
    'memory.nudge_interval': r'[^_]nudge_interval',
    'web.backend': r'get\(\s*["\']backend["\']',
    'hooks_auto_accept': r'hooks_auto_accept',
}

# Environment variables and home files janus_engine relies on.
NAMES = {
    'env JANUS_HOME': r'JANUS_HOME',
    'env JANUS_EPHEMERAL_SYSTEM_PROMPT': r'JANUS_EPHEMERAL_SYSTEM_PROMPT',
    'env JANUS_YOLO_MODE': r'JANUS_YOLO_MODE',
    'home SOUL.md': r'SOUL\.md',
    'home .no-bundled-skills': r'\.no-bundled-skills',
    'quiet mode prints session_id to stderr': r'session_id: \{[^}]*\}["\'],\s*file=sys\.stderr',
    'a lost session says "Session not found"': r'Session not found',
}

# `janus chat` options every turn passes.
CHAT_FLAGS = ('-q', '-Q', '-t', '--resume', '--source', '--provider', '-m')

# Columns read from the home's state.db (usage, recovered replies).
STATE_COLUMNS = {
    'sessions': (
        'id',
        'source',
        'model',
        'parent_session_id',
        'started_at',
        'input_tokens',
        'output_tokens',
        'cache_read_tokens',
        'cache_write_tokens',
        'reasoning_tokens',
        'estimated_cost_usd',
        'api_call_count',
    ),
    'messages': ('id', 'session_id', 'role', 'content', 'timestamp'),
}

# Shown, never required: the step display and notice stripping degrade quietly.
SOFT_NAMES = {
    'notice "Reached maximum iterations"': r'Reached maximum iterations',
    'notice "All API retries exhausted"': r'All API retries exhausted',
}

_SOURCE_PACKAGES = ('agent', 'tools', 'janus_cli')
_SOURCE_MODULES = (
    'cli.py',
    'run_agent.py',
    'janus_state.py',
    'janus_constants.py',
    'model_tools.py',
    'toolsets.py',
)


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.notes: list[str] = []

    def check(self, name: str, ok: bool, detail: str = '', *, required: bool = True) -> None:
        self.checks.append({'name': name, 'ok': bool(ok), 'required': required, 'detail': detail})

    @property
    def ok(self) -> bool:
        return all(c['ok'] for c in self.checks if c['required'])


def _source_root() -> Path | None:
    try:
        import toolsets  # noqa: PLC0415 — Janus's module, in Janus's venv
    except Exception:  # noqa: BLE001
        return None
    return Path(toolsets.__file__).resolve().parent


def _sources(root: Path) -> list[str]:
    texts = []
    files = [root / m for m in _SOURCE_MODULES]
    for package in _SOURCE_PACKAGES:
        files.extend(sorted((root / package).rglob('*.py')))
    for path in files:
        try:
            texts.append(path.read_text(encoding='utf-8', errors='ignore'))
        except OSError:
            continue
    return texts


def _found(texts: list[str], pattern: str) -> bool:
    rx = re.compile(pattern)
    return any(rx.search(t) for t in texts)


def _check_toolsets(report: Report) -> None:
    try:
        import toolsets  # noqa: PLC0415

        known = toolsets.TOOLSETS
    except Exception as e:  # noqa: BLE001
        report.check('toolsets load', False, str(e)[:200])
        return
    for name, allowed in TOOLSETS.items():
        entry = known.get(name)
        if not isinstance(entry, dict):
            report.check(f'toolset {name}', False, 'missing')
            continue
        tools = set(entry.get('tools') or [])
        extra = sorted(tools - allowed)
        nested = entry.get('includes') or []
        detail = ', '.join(f'+{t}' for t in extra) or (
            'includes ' + ', '.join(nested) if nested else ''
        )
        report.check(f'toolset {name}', bool(tools) and not extra and not nested, detail)


def _check_hooks(report: Report) -> None:
    try:
        from agent.shell_hooks import iter_configured_hooks  # noqa: PLC0415
        from janus_cli.plugins import VALID_HOOKS  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        report.check('tool hooks', False, str(e)[:200], required=False)
        return
    events = {'pre_tool_call', 'post_tool_call'}
    report.check('tool hook events', events <= set(VALID_HOOKS), required=False)
    cfg = {
        'hooks': {e: [{'command': 'python hook.py progress.jsonl', 'timeout': 5}] for e in events}
    }
    try:
        specs = iter_configured_hooks(cfg)
        parsed = {s.event for s in specs}
    except Exception as e:  # noqa: BLE001
        parsed, detail = set(), str(e)[:200]
    else:
        detail = ''
    report.check('tool hooks parse from config', parsed == events, detail, required=False)


def _check_state(report: Report, texts: list[str]) -> None:
    for table, columns in STATE_COLUMNS.items():
        body = ''
        for t in texts:
            m = re.search(rf'CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\);', t, re.S)
            if m:
                body = m.group(1)
                break
        missing = [c for c in columns if not re.search(rf'^\s*{c}\s', body, re.M)]
        report.check(f'state.db {table} columns', bool(body) and not missing, ', '.join(missing))


def _check_cli(report: Report, janus: Path) -> None:
    if not janus.is_file():
        report.check('janus chat options', False, f'no {janus}')
        return
    with tempfile.TemporaryDirectory() as home:
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': home, 'JANUS_HOME': home}
        try:
            proc = subprocess.run(  # noqa: S603 — the install's own entry point
                [str(janus), 'chat', '--help'],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
                check=False,
            )
            text = proc.stdout + proc.stderr
        except (OSError, subprocess.SubprocessError) as e:
            report.check('janus chat options', False, str(e)[:200])
            return
    missing = [
        f
        for f in CHAT_FLAGS
        if not re.search(rf'(^|[\s,\[]){re.escape(f)}([\s,=\]]|$)', text, re.M)
    ]
    report.check('janus chat options', not missing, ', '.join(missing))


def _check_imports(report: Report) -> None:
    for module, why in (('mcp', 'store tools over MCP'), ('ddgs', 'web search')):
        try:
            __import__(module)
        except Exception as e:  # noqa: BLE001
            report.check(f'import {module}', False, f'{why}: {str(e)[:150]}')
        else:
            report.check(f'import {module}', True, why)


def _notes(report: Report, root: Path) -> None:
    delegate = root / 'tools' / 'delegate_tool.py'
    try:
        if 'acp_command' in delegate.read_text(encoding='utf-8', errors='ignore'):
            report.notes.append('delegate_task still takes acp_command: subagents stay off')
    except OSError:
        pass
    review = root / 'agent' / 'background_review.py'
    try:
        if 'redirect_stdout' in review.read_text(encoding='utf-8', errors='ignore'):
            report.notes.append('background review still swaps stdout: nudges stay 0')
    except OSError:
        pass


def _version() -> str:
    try:
        from importlib.metadata import version  # noqa: PLC0415

        return version('janus-agent')
    except Exception:  # noqa: BLE001
        return ''


def run(janus: Path | None = None) -> Report:
    """Check the install this Python belongs to; ``janus`` defaults to its entry point."""
    report = Report()
    root = _source_root()
    if root is None:
        report.check('janus importable', False, 'toolsets module not found')
        return report
    texts = _sources(root)
    _check_toolsets(report)
    for key, pattern in CONFIG_KEYS.items():
        report.check(f'config {key}', _found(texts, pattern))
    for name, pattern in NAMES.items():
        report.check(name, _found(texts, pattern))
    for name, pattern in SOFT_NAMES.items():
        report.check(name, _found(texts, pattern), required=False)
    _check_state(report, texts)
    _check_hooks(report)
    _check_imports(report)
    _check_cli(report, janus or Path(sys.executable).with_name('janus'))
    _notes(report, root)
    return report


def main(argv: list[str]) -> int:
    janus = Path(argv[argv.index('--janus') + 1]) if '--janus' in argv[:-1] else None
    report = run(janus)
    print(
        json.dumps(
            {
                'ok': report.ok,
                'version': _version(),
                'checks': report.checks,
                'notes': report.notes,
            },
            indent=1,
        )
    )
    return 0 if report.ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
