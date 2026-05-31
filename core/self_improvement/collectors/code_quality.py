"""code_quality collector — deterministic static-analysis sweep.

Phase 1 ships the cheapest, highest-signal tier: ``ruff`` (already a
hard dep) + ``bandit`` (already in pre-commit). Both emit JSON output
that we parse into Signal rows — one per finding, fingerprinted by
``rule:file:line`` so a single rule violation on the same line dedups
across runs.

Phase 2 will add mypy / vulture / radon / jscpd. They're cheap to add
once we prove the pipeline reads-out cleanly in the dashboard.

Cost model: weekly cadence (Mon 05:00 UTC). On a 100k-LOC codebase
ruff + bandit complete in seconds; cost is wall-clock, not money.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

from django.conf import settings

from core.self_improvement.collectors.base import Collector, Signal
from core.self_improvement.services import fingerprint_for

logger = logging.getLogger('morpheus.self_improvement.code_quality')

SOURCE = 'code_quality'

# Where the repo lives at runtime. settings.BASE_DIR is the canonical
# answer in Morpheus.
DEFAULT_REPO_ROOT = Path(getattr(settings, 'BASE_DIR', '.'))

# Paths scanned. Stays inside the source tree; avoids vendored deps,
# build artefacts, and tests (tests are scanned by a separate collector
# in Phase 2).
SCAN_PATHS = ('core', 'plugins', 'api', 'morph')

# Severity buckets for ruff codes. Anything not listed gets DEFAULT.
RUFF_SEVERITY = {
    'E': 35,  # pycodestyle errors — style only
    'F': 60,  # pyflakes — real bugs (undefined name, unused import)
    'B': 55,  # flake8-bugbear — likely bugs
    'S': 75,  # flake8-bandit — security
    'PLE': 65,  # pylint errors
    'PLW': 45,  # pylint warnings
}
RUFF_DEFAULT_SEVERITY = 40

# Bandit severity → numeric.
BANDIT_SEVERITY = {'HIGH': 80, 'MEDIUM': 60, 'LOW': 35}


class CodeQualityCollector(Collector):
    name = SOURCE

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or DEFAULT_REPO_ROOT

    def run(self) -> Iterable[Signal]:
        yield from self._run_ruff()
        yield from self._run_bandit()

    # ------------------------------------------------------------------

    def _run_ruff(self) -> Iterable[Signal]:
        if shutil.which('ruff') is None:
            logger.warning('code_quality: ruff not on PATH; skipping ruff sweep')
            return
        cmd = ['ruff', 'check', '--output-format=json', *SCAN_PATHS]
        findings = self._run_json_command(cmd)
        if findings is None:
            return
        for f in findings:
            code = (f.get('code') or '?').strip()
            path = self._relative_path(f.get('filename', ''))
            line = (f.get('location') or {}).get('row', 0)
            message = (f.get('message') or '')[:300]
            yield Signal(
                source=SOURCE,
                fingerprint=fingerprint_for(SOURCE, 'ruff', code, path, line),
                severity=self._severity_for_ruff(code),
                payload={
                    'tool': 'ruff',
                    'rule': code,
                    'path': path,
                    'line': line,
                    'message': message,
                    'fixable': bool(f.get('fix') is not None),
                },
            )

    def _run_bandit(self) -> Iterable[Signal]:
        if shutil.which('bandit') is None:
            logger.warning('code_quality: bandit not on PATH; skipping bandit sweep')
            return
        # -q quiets the banner; -f json gives us a structured envelope;
        # -r recurses; -ll surfaces medium+ only (low is noise).
        cmd = [
            'bandit',
            '-q',
            '-f',
            'json',
            '-r',
            '-ll',
            '-x',
            'tests,migrations,venv,node_modules,vendor',
            *SCAN_PATHS,
        ]
        envelope = self._run_json_command(cmd, allow_nonzero=True)
        if envelope is None:
            return
        for f in envelope.get('results', []) or []:
            severity_label = (f.get('issue_severity') or 'LOW').upper()
            confidence_label = (f.get('issue_confidence') or 'LOW').upper()
            test_id = f.get('test_id', '?')
            path = self._relative_path(f.get('filename', ''))
            line = f.get('line_number', 0)
            yield Signal(
                source=SOURCE,
                fingerprint=fingerprint_for(SOURCE, 'bandit', test_id, path, line),
                severity=BANDIT_SEVERITY.get(severity_label, 40),
                payload={
                    'tool': 'bandit',
                    'rule': test_id,
                    'rule_name': f.get('test_name', ''),
                    'path': path,
                    'line': line,
                    'severity_label': severity_label,
                    'confidence': confidence_label,
                    'message': (f.get('issue_text') or '')[:300],
                },
            )

    # ------------------------------------------------------------------

    def _run_json_command(
        self, cmd: list[str], *, allow_nonzero: bool = True
    ) -> list | dict | None:
        """Run cmd, parse stdout as JSON. Returns ``None`` on parse
        failure or unexpected error so the collector can keep going.

        ruff returns non-zero when it finds issues — that's the normal
        case, not a failure. bandit same.
        """
        try:
            proc = subprocess.run(  # noqa: S603 — args are static, no shell
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning('code_quality: %s failed: %s', cmd[0], exc)
            return None

        if not allow_nonzero and proc.returncode != 0:
            logger.warning(
                'code_quality: %s returned %d; stderr=%s',
                cmd[0],
                proc.returncode,
                proc.stderr[:300],
            )
            return None

        if not proc.stdout.strip():
            return []
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            logger.warning('code_quality: %s produced non-JSON output: %s', cmd[0], exc)
            return None

    def _relative_path(self, abs_path: str) -> str:
        """Strip the repo root so paths read as `core/...` not
        `/home/runner/work/morph/core/...`."""
        if not abs_path:
            return ''
        try:
            return str(Path(abs_path).resolve().relative_to(self.repo_root.resolve()))
        except (ValueError, OSError):
            return abs_path[-200:]

    @staticmethod
    def _severity_for_ruff(code: str) -> int:
        # Ruff codes are prefix + digits, e.g. `E501`, `F401`, `PLE0101`.
        for prefix in ('PLE', 'PLW'):
            if code.startswith(prefix):
                return RUFF_SEVERITY[prefix]
        if code and code[0] in RUFF_SEVERITY:
            return RUFF_SEVERITY[code[0]]
        return RUFF_DEFAULT_SEVERITY
