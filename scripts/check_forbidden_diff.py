#!/usr/bin/env python3
"""Pre-commit gate: scan staged ADDED lines for the human-applicable subset
of the safety boundary's forbidden diff patterns (hardcoded secrets, raw
destructive SQL, os.system). See core/safety.py PRECOMMIT_FORBIDDEN_PATTERNS.

Deliberately NOT the full boundary — PROTECTED_PATHS covers all of core/
and FORBIDDEN_DIFF_PATTERNS includes idioms (`.delete()`, `subprocess.`)
that are legitimate in hand-written code. Those stay runtime AI gates.

Exit 0 = clean, 1 = violation(s) printed. Bypass: SKIP_HOOK=1.
Pure stdlib + core.safety (which is Django-free by design).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.safety import PRECOMMIT_FORBIDDEN_PATTERNS  # noqa: E402

_COMPILED = tuple(re.compile(p) for p in PRECOMMIT_FORBIDDEN_PATTERNS)


def added_lines(diff_text: str) -> list[tuple[str, str]]:
    """(file, line) pairs for every line the staged diff ADDS."""
    out: list[tuple[str, str]] = []
    current = ''
    for line in diff_text.splitlines():
        if line.startswith('+++ b/'):
            current = line[6:]
        elif line.startswith('+') and not line.startswith('+++'):
            out.append((current, line[1:]))
    return out


def main() -> int:
    diff = subprocess.run(  # noqa: S603 — fixed argv, no shell, hook context
        ['git', 'diff', '--cached', '--unified=0'],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    violations = []
    for path, line in added_lines(diff):
        # The boundary's own definitions, its contract tests, and this
        # script legitimately contain the patterns as source text.
        if path in (
            'core/safety.py',
            'core/self_improvement/tests/test_safety_boundary.py',
            'scripts/check_forbidden_diff.py',
        ):
            continue
        for pat in _COMPILED:
            if pat.search(line):
                violations.append(
                    f'{path}: forbidden pattern {pat.pattern!r} in: {line.strip()[:120]}'
                )
    if violations:
        print('[check_forbidden_diff] staged diff crosses the safety boundary:')
        for v in violations:
            print(f'  ✗ {v}')
        print('  (hardcoded secrets / destructive SQL / os.system must not be committed)')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
