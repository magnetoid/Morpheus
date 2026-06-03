"""Git-based platform update-check — phase 3 of the updating system.

Self-hosted Morpheus runs from a git checkout, so "is an update available?"
= is the tracked upstream ahead of the deployed HEAD. Read-only + fail-soft:
with no ``.git`` (a built container image, a tarball install) it reports
``unavailable`` rather than erroring. Channel = git refs/tags (decided
2026-06-03). Apply/rollback is phase 4 and routes through ``core/safety.py``.

All git calls are fixed-arg ``subprocess`` (no shell), timeout-bounded, and
read-only except an explicit ``fetch`` which only updates remote refs (never
the working tree / code).
"""

# ruff: noqa: PLC0415, S603, S607
# S603/S607: git is invoked with fixed, internal args (no shell, no user
# input) against the repo root — the subprocess warnings are false positives.

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(args: list[str], cwd: Path, timeout: int = 10) -> str | None:
    try:
        result = subprocess.run(
            ['git', *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:  # noqa: BLE001 — git missing / timeout → treat as unknown
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _repo_root() -> Path:
    from django.conf import settings

    return Path(getattr(settings, 'BASE_DIR', '.'))


def platform_update_status(*, fetch: bool = False) -> dict:
    """Compare the deployed git checkout against its upstream.

    Returns ``{source, available, current, sha, branch, upstream, behind,
    ahead, latest, reason?}``. ``available`` ∈ {yes, no, unknown, unavailable}.
    ``fetch=True`` refreshes remote refs first (network; best-effort).
    """
    root = _repo_root()
    if not (root / '.git').exists():
        return {
            'source': 'git',
            'available': 'unavailable',
            'reason': 'No git metadata in this deployment (built image / non-git install).',
        }
    if fetch:
        _git(['fetch', '--quiet'], root, timeout=30)

    out: dict = {
        'source': 'git',
        'current': _git(['describe', '--tags', '--always', '--dirty'], root) or 'unknown',
        'sha': _git(['rev-parse', '--short', 'HEAD'], root) or '',
        'branch': _git(['rev-parse', '--abbrev-ref', 'HEAD'], root) or '',
    }
    upstream = _git(['rev-parse', '--abbrev-ref', '@{u}'], root)
    out['upstream'] = upstream or ''
    if not upstream:
        out['available'] = 'unknown'
        out['reason'] = 'No upstream tracking branch configured.'
        return out

    behind = _git(['rev-list', '--count', f'HEAD..{upstream}'], root)
    ahead = _git(['rev-list', '--count', f'{upstream}..HEAD'], root)
    out['behind'] = int(behind) if (behind or '').isdigit() else 0
    out['ahead'] = int(ahead) if (ahead or '').isdigit() else 0
    out['latest'] = _git(['describe', '--tags', '--always', upstream], root) or ''
    out['available'] = 'yes' if out['behind'] > 0 else 'no'
    return out
