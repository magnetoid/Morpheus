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


def _git_ok(args: list[str], cwd: Path, timeout: int = 10) -> bool:
    """Run git for its exit code only (e.g. merge-base --is-ancestor)."""
    try:
        result = subprocess.run(
            ['git', *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:  # noqa: BLE001
        return False
    return result.returncode == 0


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


def apply_platform_update(*, confirm: bool = False, run_migrations: bool = True) -> dict:  # noqa: PLR0911
    """Fast-forward the deployed checkout to its upstream — phase 4.

    Conservative + reliable by construction:
      * **dry-run by default** — without ``confirm=True`` it only returns a
        plan and mutates nothing.
      * **opt-in** — even with ``confirm`` it refuses unless
        ``settings.MORPHEUS_SELF_UPDATE_ENABLED`` is on.
      * **fast-forward only** — aborts if local has diverged (never force).
      * **backup first** (``morph_backup``), then ``git merge --ff-only`` →
        ``migrate`` → ``check``; any failure **rolls the code back** to the
        prior commit. (DB migrations are not auto-reversed — the pre-update
        backup is the restore point; this is reported loudly.)
      * **inert** where there's no ``.git`` (built container) → ``unavailable``.

    CLI-only (``manage.py morph_apply_update``); deliberately not web-triggerable.
    """
    from django.conf import settings

    root = _repo_root()
    if not (root / '.git').exists():
        return {
            'ok': False,
            'status': 'unavailable',
            'reason': 'No git metadata in this deployment.',
        }

    status = platform_update_status(fetch=True)
    if status.get('available') == 'no':
        return {
            'ok': True,
            'status': 'noop',
            'message': 'Already up to date.',
            'current': status.get('current'),
        }
    if status.get('available') != 'yes':
        return {
            'ok': False,
            'status': status.get('available', 'unknown'),
            'reason': status.get('reason', 'Update status could not be determined.'),
        }

    upstream = status['upstream']
    prior_sha = _git(['rev-parse', 'HEAD'], root) or ''
    plan = {
        'from': status.get('current'),
        'to': status.get('latest'),
        'behind': status.get('behind'),
        'upstream': upstream,
    }

    if not confirm:
        return {
            'ok': True,
            'status': 'dry_run',
            'plan': plan,
            'message': 'Dry run — pass confirm=True (CLI: --confirm) to apply.',
        }

    if not getattr(settings, 'MORPHEUS_SELF_UPDATE_ENABLED', False):
        return {
            'ok': False,
            'status': 'disabled',
            'plan': plan,
            'reason': 'Self-update is disabled. Set MORPHEUS_SELF_UPDATE_ENABLED=1 to allow.',
        }

    # Fast-forward only: HEAD must be an ancestor of upstream.
    if not _git_ok(['merge-base', '--is-ancestor', 'HEAD', upstream], root):
        return {
            'ok': False,
            'status': 'diverged',
            'plan': plan,
            'reason': 'Local has diverged from upstream; fast-forward not possible. Resolve manually.',
        }

    from django.core.management import call_command

    try:
        call_command('morph_backup')
    except Exception:  # noqa: BLE001 — proceed even if backup is unavailable, but note it
        plan['backup'] = 'failed'

    if not _git_ok(['merge', '--ff-only', upstream], root):
        return {
            'ok': False,
            'status': 'apply_failed',
            'plan': plan,
            'reason': 'git fast-forward failed; working tree unchanged.',
        }

    def _rollback(reason: str) -> dict:
        _git_ok(['reset', '--hard', prior_sha], root)
        return {'ok': False, 'status': 'rolled_back', 'plan': plan, 'reason': reason}

    if run_migrations:
        try:
            call_command('migrate', '--noinput')
        except Exception as e:  # noqa: BLE001
            return _rollback(
                f'migrate failed ({str(e)[:160]}); code reverted to {prior_sha[:7]}. '
                'REVIEW DB — restore the pre-update backup if needed.'
            )

    try:
        call_command('check')
    except Exception as e:  # noqa: BLE001
        return _rollback(f'post-update healthcheck failed ({str(e)[:160]}); code reverted.')

    return {
        'ok': True,
        'status': 'applied',
        'from': prior_sha[:7],
        'to': status.get('latest'),
        'plan': plan,
    }
