"""Platform update-check and apply — phases 3 and 4 of the updating system.

The signed channel (``core/update_sources.py``, morpheus.direct) is read first.
Git is the fallback: a checkout with no signed channel asks whether its tracked
upstream is ahead of the deployed HEAD. Read-only + fail-soft: with no ``.git``
(a built container image, a tarball install) it reports ``unavailable`` rather
than erroring. Apply/rollback routes through ``core/safety.py``.

All git calls are fixed-arg ``subprocess`` (no shell), timeout-bounded, and
read-only except an explicit ``fetch`` which only updates remote refs (never
the working tree / code).
"""

# ruff: noqa: PLC0415, S603, S607
# S603/S607: git is invoked with fixed, internal args (no shell, no user
# input) against the repo root — the subprocess warnings are false positives.

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

# Dependency manifests — if any of these change upstream, an in-place git apply
# is unsafe (it doesn't pip-install), so we refuse unless explicitly allowed.
_DEP_FILES = (
    'requirements.txt',
    'requirements.lock.txt',
    'requirements/',
    'pyproject.toml',
    'poetry.lock',
)


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


def can_self_update() -> bool:
    """True when this install can update its own code: a git checkout with git installed.

    A built image cannot: our stores' images carry no ``.git``, and the Dockerfile
    purges git, so an image built from a clone keeps ``.git`` without the tool. It
    updates when a new version is released and deployed, so the dashboard and
    Linda offer no "Update now" there.
    """
    return (_repo_root() / '.git').exists() and shutil.which('git') is not None


def update_path() -> str:
    """How this install updates its own code: 'git' (fast-forward) or 'manual'."""
    return 'git' if can_self_update() else 'manual'


def current_view(status: dict) -> dict:
    """A cached channel status, restated against the version running now.

    The cache outlives a deploy, so "vX is out" can be stale the moment a store
    takes vX. Returns a copy whose ``current`` is the running version and, for a
    manifest answer, whose ``available`` is re-derived from it.
    """
    from core.update_sources import is_newer
    from core.versioning import core_version

    out = {**status, 'current': core_version()}
    if (
        status.get('source') == 'manifest'
        and status.get('available') in ('yes', 'no')
        and status.get('latest')
    ):
        out['available'] = 'yes' if is_newer(status['latest'], core_version()) else 'no'
    return out


def _not_checked_yet(source: str, path: str) -> dict:
    from core.versioning import core_version

    return {
        'source': source,
        'available': 'unknown',
        'reason': 'Not checked yet. The store checks once a day; Check for updates checks now.',
        'current': core_version(),
        'components': [],
        'path': path,
    }


def platform_update_status(*, fetch: bool = False) -> dict:  # noqa: PLR0911
    """Where this install stands against the update channel.

    Checks switched off (``MORPHEUS_UPDATE_MANIFEST_URL=off``) answer first and
    touch nothing: no git, no network. A signed manifest source is asked next:
    ``fetch=True`` asks it (network), a page load (``fetch=False``) reads the
    cached answer, restated against the running version, and never fetches.
    A repository source on an install with no git metadata works the same way.
    Otherwise compares the deployed git checkout against its upstream.
    Returns ``{source, available, current, ..., path}``; ``available`` is one
    of yes, no, unknown, unavailable; ``path`` is ``update_path()``.
    ``fetch=True`` refreshes git's remote refs only on the git branch (best-effort).
    """
    from core.update_sources import (
        SignedManifestSource,
        check_for_update,
        checks_off,
        configured_source,
    )
    from core.versioning import core_version

    path = update_path()
    if checks_off():
        return {**check_for_update(core_version()), 'path': path}
    source = configured_source()
    if isinstance(source, SignedManifestSource):
        if fetch:
            return {**check_for_update(core_version()), 'path': path}
        cached = cached_update_status()
        if cached and cached.get('source') == 'manifest':
            return {**current_view(cached), 'path': path}
        return _not_checked_yet('manifest', path)

    root = _repo_root()
    if not (root / '.git').exists():
        # No git metadata: a built image. A repository source
        # (MORPHEUS_UPDATE_REPO) is asked before giving up, but a page load
        # reads the daily answer instead of calling GitHub.
        if source is not None:
            if fetch:
                return {**check_for_update(core_version()), 'path': path}
            cached = cached_update_status()
            if cached and cached.get('source') == source.name:
                return {**current_view(cached), 'path': path}
            return _not_checked_yet(source.name, path)
        return {
            'source': 'git',
            'available': 'unavailable',
            'reason': 'No git metadata in this deployment (built image / non-git install).',
            'path': path,
        }
    if fetch:
        _git(['fetch', '--quiet'], root, timeout=30)

    out: dict = {
        'source': 'git',
        'current': _git(['describe', '--tags', '--always', '--dirty'], root) or 'unknown',
        'sha': _git(['rev-parse', '--short', 'HEAD'], root) or '',
        'branch': _git(['rev-parse', '--abbrev-ref', 'HEAD'], root) or '',
        'path': path,
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


_UPDATE_STATUS_CACHE_KEY = 'morpheus:update_status'
_UPDATE_STATUS_TTL = 60 * 60 * 36  # 36h — survives a missed daily run


def refresh_update_status() -> dict:
    """Fetch the live update status (network) and cache it. Called by the
    daily beat task so dashboard surfaces can show "update available" without
    a per-request git fetch. Returns the status dict."""
    from django.core.cache import cache

    status = platform_update_status(fetch=True)
    if 'components' not in status:
        # A git deployment's platform status knows nothing about apps/themes —
        # those come from the release source regardless of how core deploys.
        from core.update_sources import component_updates

        try:
            status['components'] = component_updates()
        except Exception:  # noqa: BLE001 — a component check must never blank the platform status
            status['components'] = []
    cache.set(_UPDATE_STATUS_CACHE_KEY, status, _UPDATE_STATUS_TTL)
    return status


def cached_update_status() -> dict | None:
    """Last cached update status (from the daily check), or None if the check
    hasn't run yet. Cheap — no git/network. Surfaces read this."""
    from django.core.cache import cache

    return cache.get(_UPDATE_STATUS_CACHE_KEY)


def _dependency_changes(root: Path, upstream: str) -> list[str]:
    """Dependency-manifest files that differ between HEAD and upstream. A
    non-empty list means an in-place apply would run new code against
    not-yet-installed packages (the native-dep landmine) — caller refuses."""
    out = _git(['diff', '--name-only', f'HEAD..{upstream}', '--', *_DEP_FILES], root, timeout=20)
    return [line for line in (out or '').splitlines() if line.strip()]


def _boot_probe(root: Path) -> tuple[bool, str]:
    """Run ``manage.py check`` in a FRESH interpreter so the *new* (post-merge)
    code is actually re-imported. The in-process ``check`` runs in the
    already-loaded old process and cannot catch a settings-import / bad-import /
    native-dep crash in the new code — this can. Returns ``(ok, output_tail)``."""
    try:
        proc = subprocess.run(  # noqa: S603 — static args, repo-root cwd
            [sys.executable, 'manage.py', 'check'],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 — a failed probe = treat as not-bootable
        return False, str(exc)[:400]
    ok = proc.returncode == 0
    return ok, (proc.stderr or proc.stdout or '')[-400:]


def apply_platform_update(  # noqa: PLR0911, PLR0912
    *, confirm: bool = False, run_migrations: bool = True, allow_dependency_changes: bool = False
) -> dict:
    """Fast-forward the deployed checkout to the release's commit (the signed
    channel's), else to its upstream — phase 4.

    Conservative + reliable by construction:
      * **dry-run by default** — without ``confirm=True`` it only returns a
        plan and mutates nothing.
      * **opt-in** — even with ``confirm`` it refuses unless
        ``settings.MORPHEUS_SELF_UPDATE_ENABLED`` is on.
      * **fast-forward only** — aborts if local has diverged (never force).
      * **dependency guard** — refuses (``deps_changed``) if upstream changed
        a dependency manifest, because in-place apply can't pip-install (the
        native-dep landmine); rebuild the image instead, or pass
        ``allow_dependency_changes`` once you've installed them.
      * **backup first** (``morph_backup``), then ``git merge --ff-only`` →
        **boot-probe** (``manage.py check`` in a *fresh* interpreter, so the
        new code is actually re-imported — runs **before** ``migrate`` so a
        non-bootable update reverts with the DB untouched) → ``migrate`` →
        in-process ``check``; any failure **rolls the code back** to the prior
        commit. (DB migrations are not auto-reversed — the pre-update backup is
        the restore point; this is reported loudly.)
      * **inert** where there's no ``.git`` (built container) → ``unavailable``.
    """
    from django.conf import settings

    root = _repo_root()
    if not (root / '.git').exists():
        return {
            'ok': False,
            'status': 'unavailable',
            'reason': 'No git metadata in this deployment.',
        }
    if not can_self_update():
        return {
            'ok': False,
            'status': 'unavailable',
            'reason': (
                'This install cannot update its own code (git is not installed). '
                'Take the new version as a new image.'
            ),
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

    # The channel names the commit to move to; a git source moves to its upstream.
    from_channel = status.get('source') == 'manifest'
    target = status.get('commit') if from_channel else status['upstream']
    if from_channel and not re.fullmatch(r'[0-9a-f]{40}', target or ''):
        return {
            'ok': False,
            'status': 'no_commit',
            'reason': 'The release names no commit to update to.',
        }
    prior_sha = _git(['rev-parse', 'HEAD'], root) or ''
    plan = {
        'from': status.get('current'),
        'to': status.get('latest'),
        'behind': status.get('behind'),
        'target': target,
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

    if from_channel:
        # The commit may not be in the checkout yet: fetch exactly that one.
        _git(['fetch', '--quiet', 'origin', target], root, timeout=60)
        if not _git_ok(['cat-file', '-e', f'{target}^{{commit}}'], root):
            return {
                'ok': False,
                'status': 'apply_failed',
                'plan': plan,
                'reason': "Could not fetch the release's commit.",
            }
        diverged = "The release's commit is not a later commit than this checkout. Update by hand."
    else:
        diverged = 'Local has diverged from upstream; fast-forward not possible. Resolve manually.'

    # Fast-forward only: HEAD must be an ancestor of the target.
    if not _git_ok(['merge-base', '--is-ancestor', 'HEAD', target], root):
        return {'ok': False, 'status': 'diverged', 'plan': plan, 'reason': diverged}

    # Dependency guard — an in-place git apply does NOT pip-install, so if
    # upstream changed requirements the new code would import missing/native
    # packages and crash at boot. Refuse (rebuild the image instead) unless
    # the caller explicitly accepts responsibility for installing them.
    dep_changes = _dependency_changes(root, target)
    if dep_changes and not allow_dependency_changes:
        return {
            'ok': False,
            'status': 'deps_changed',
            'plan': {**plan, 'dependency_files': dep_changes},
            'reason': (
                'Upstream changed dependencies (' + ', '.join(dep_changes) + '). In-place apply '
                'cannot install packages — rebuild/redeploy the image, or re-run with '
                'allow_dependency_changes=True after installing them.'
            ),
        }

    from django.core.management import call_command

    try:
        call_command('morph_backup')
    except Exception:  # noqa: BLE001 — proceed even if backup is unavailable, but note it
        plan['backup'] = 'failed'

    if not _git_ok(['merge', '--ff-only', target], root, timeout=120):
        head_now = _git(['rev-parse', 'HEAD'], root) or ''
        if head_now == prior_sha:
            reason = 'git fast-forward failed; working tree unchanged.'
        else:
            reason = (
                f'git fast-forward failed part way; HEAD is now {head_now[:7] or "unknown"} '
                f'(it was {prior_sha[:7]}). Check the checkout by hand.'
            )
        return {'ok': False, 'status': 'apply_failed', 'plan': plan, 'reason': reason}

    def _rollback(reason: str) -> dict:
        _git_ok(['reset', '--hard', prior_sha], root)
        return {'ok': False, 'status': 'rolled_back', 'plan': plan, 'reason': reason}

    # Boot-probe the NEW code in a fresh interpreter BEFORE migrating — the DB
    # is still untouched, so a non-bootable update rolls back the code with zero
    # schema risk. Catches settings-import / bad-import / native-dep crashes the
    # in-process check (old code, already loaded) cannot see.
    boot_ok, boot_tail = _boot_probe(root)
    if not boot_ok:
        return _rollback(
            f'new code failed to boot ({boot_tail[:160]}); code reverted, DB untouched.'
        )

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
