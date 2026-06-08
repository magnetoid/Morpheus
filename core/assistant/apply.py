"""Linda self-dev — Phase 4 APPLY: an owner-approved CodeProposal → code on a
git BRANCH (never main), behind every gate. Policy: ADR 0014. Shipped DORMANT —
``apply_enabled()`` is False unless ``MORPHEUS_SELF_UPDATE_ENABLED`` is set, so
the whole path is inert by default.

Design notes:
  * The branch commit is built with git PLUMBING (hash-object + a temporary
    index + commit-tree + branch) so the LIVE working tree and current HEAD are
    never touched — the generated file exists ONLY on the new branch, awaiting a
    staging deploy / human merge (Phase 7). No checkout, no HEAD switch.
  * Every gate is re-checked at apply time against the CURRENT source (not the
    draft-time scan) and against core/safety.py — the single boundary, which
    self-dev reads and can never widen.
  * apply_proposal() NEVER raises; it audits + returns a structured result.
"""

# S603/S607: git is invoked with fixed, internal args (no shell, no user input
# in argv) against the repo root — the subprocess warnings are false positives.
# _write_branch is a chain of git-step error guards → many early returns (PLR0911).
# ruff: noqa: S603, S607, PLC0415, PLR0911
from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path

logger = logging.getLogger('morpheus.assistant.apply')

# Repo root: core/assistant/apply.py → parents[2].
REPO_ROOT = Path(__file__).resolve().parents[2]

ENABLE_FLAG = 'MORPHEUS_SELF_UPDATE_ENABLED'
MAX_APPLIES_PER_DAY = 5
ALLOWED_PREFIX = 'plugins/installed/'
_BRANCH_PREFIX = 'selfdev/'

_GIT_AUTHOR_ENV = {
    'GIT_AUTHOR_NAME': 'Linda (selfdev)',
    'GIT_AUTHOR_EMAIL': 'selfdev@morpheus.local',
    'GIT_COMMITTER_NAME': 'Linda (selfdev)',
    'GIT_COMMITTER_EMAIL': 'selfdev@morpheus.local',
}


def apply_enabled() -> bool:
    """The master kill switch (ADR 0014). Default OFF — the whole apply path is
    inert until ops sets the env var. Linda / the dashboard can never flip it."""
    return os.environ.get(ENABLE_FLAG, '').strip().lower() in ('1', 'true', 'yes', 'on')


def _git(
    args: list[str], *, stdin: str | None = None, env_extra: dict | None = None, timeout: int = 15
) -> tuple[int, str]:
    """Run git with fixed args (no shell). Returns (returncode, stdout-or-stderr)."""
    env = {**os.environ, **(env_extra or {})}
    try:
        result = subprocess.run(
            ['git', *args],
            cwd=REPO_ROOT,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except Exception as e:  # noqa: BLE001 — git missing / timeout → treat as failure
        return 1, f'git invocation failed: {e}'
    out = (result.stdout or '').strip()
    return result.returncode, out if result.returncode == 0 else (result.stderr or out).strip()


def _is_git_repo() -> bool:
    return (REPO_ROOT / '.git').exists()


def _applies_last_24h() -> int:
    from django.utils import timezone

    from core.assistant.models import CodeProposal

    since = timezone.now() - timedelta(hours=24)
    return CodeProposal.objects.filter(status='applied', applied_at__gte=since).count()


def preflight(proposal) -> list[str]:
    """Return the list of reasons this proposal may NOT be applied. Empty list =
    every gate is clear. Re-checks the CURRENT source against core/safety.py."""
    from core.assistant.codegen import passed, scan_source
    from core.safety import find_violations, is_path_protected

    reasons: list[str] = []

    # 1. Master kill switch.
    if not apply_enabled():
        reasons.append('self-update disabled (MORPHEUS_SELF_UPDATE_ENABLED unset)')

    # 2. Owner approval — the binding human step.
    if proposal.status != 'approved':
        reasons.append(f'not owner-approved (status={proposal.status!r})')

    # 3. Static safety scan, re-run on current source.
    if not passed(scan_source(proposal.source, kind=proposal.kind or 'tool')):
        reasons.append('static safety scan failed (CRITICAL/HIGH findings)')

    # 4. Consensus — advisory but required to be a satisfied quorum.
    decision = (proposal.consensus or {}).get('decision')
    if decision != 'approved':
        reasons.append(f'consensus not satisfied (decision={decision!r}; need "approved")')

    # 5. Path boundary — under plugins/installed/, a .py, never protected.
    target = (proposal.target_path or '').removeprefix('./')
    if not target.startswith(ALLOWED_PREFIX):
        reasons.append(f'target outside {ALLOWED_PREFIX!r}: {target!r}')
    elif not target.endswith('.py'):
        reasons.append(f'target is not a .py file: {target!r}')
    elif is_path_protected(target):
        reasons.append(f'protected path: {target!r}')
    elif '..' in Path(target).parts:
        reasons.append('target path traversal (..) rejected')

    # 6. Forbidden patterns / magnitude on the source body (core/safety.py).
    reasons.extend(find_violations(proposal.source, [target]))

    # 7. Circuit breaker.
    if _applies_last_24h() >= MAX_APPLIES_PER_DAY:
        reasons.append(f'rate limit: {MAX_APPLIES_PER_DAY} applies/24h reached')

    return reasons


def _write_branch(proposal, target: str, branch: str) -> tuple[bool, str]:
    """Create `branch` as a commit that adds `target`=source on top of HEAD,
    using a temporary index — WITHOUT touching the working tree or HEAD.
    Returns (ok, detail)."""
    if not _is_git_repo():
        return False, 'no .git in this deployment (built image / non-git install)'

    # Refuse to clobber an existing branch.
    rc, _ = _git(['rev-parse', '--verify', '--quiet', f'refs/heads/{branch}'])
    if rc == 0:
        return False, f'branch {branch!r} already exists'

    with tempfile.NamedTemporaryFile(prefix='selfdev-index-', delete=False) as tf:
        index_path = tf.name
    try:
        idx = {'GIT_INDEX_FILE': index_path}
        # Blob → object store (from stdin; nothing written to the worktree).
        rc, blob = _git(['hash-object', '-w', '--stdin'], stdin=proposal.source)
        if rc != 0:
            return False, f'hash-object failed: {blob}'
        # Seed temp index from HEAD, add the new blob at `target`.
        rc, out = _git(['read-tree', 'HEAD'], env_extra=idx)
        if rc != 0:
            return False, f'read-tree failed: {out}'
        rc, out = _git(
            ['update-index', '--add', '--cacheinfo', f'100644,{blob},{target}'],
            env_extra=idx,
        )
        if rc != 0:
            return False, f'update-index failed: {out}'
        rc, tree = _git(['write-tree'], env_extra=idx)
        if rc != 0:
            return False, f'write-tree failed: {tree}'
        msg = f'selfdev: add {target}\n\nProposal {proposal.id} ({proposal.name}). Approved by {proposal.approver}.'
        rc, commit = _git(['commit-tree', tree, '-p', 'HEAD', '-m', msg], env_extra=_GIT_AUTHOR_ENV)
        if rc != 0:
            return False, f'commit-tree failed: {commit}'
        # NEVER main: we only ever create a fresh selfdev/* branch ref.
        rc, out = _git(['branch', branch, commit])
        if rc != 0:
            return False, f'branch create failed: {out}'
        return True, commit
    finally:
        with contextlib.suppress(OSError):
            os.unlink(index_path)


def apply_proposal(proposal) -> dict:
    """Gate → write to a NEW selfdev/* branch (never main) → audit. Never raises.
    Returns {'applied': bool, 'reason'|'branch'|'commit': ...}."""
    from core.audit import services as audit

    def _blocked(reasons: list[str]) -> dict:
        audit.record(
            event_type='selfdev.apply.blocked',
            target=str(proposal.id),
            metadata={
                'name': proposal.name,
                'reasons': reasons,
                'target_path': proposal.target_path,
            },
            severity='warning',
        )
        return {'applied': False, 'reason': '; '.join(reasons)}

    try:
        reasons = preflight(proposal)
        if reasons:
            return _blocked(reasons)

        target = proposal.target_path.removeprefix('./')
        branch = f'{_BRANCH_PREFIX}{proposal.name}-{str(proposal.id)[:8]}'
        ok, detail = _write_branch(proposal, target, branch)
        if not ok:
            return _blocked([f'git apply failed: {detail}'])

        proposal.mark_applied(branch)
        audit.record(
            event_type='selfdev.apply',
            actor=proposal.approver or None,
            target=str(proposal.id),
            metadata={
                'name': proposal.name,
                'branch': branch,
                'commit': detail,
                'target_path': target,
            },
            severity='warning',
        )
        return {'applied': True, 'branch': branch, 'commit': detail, 'target_path': target}
    except Exception as e:  # noqa: BLE001 — apply must never raise into the agent loop
        logger.exception('selfdev apply_proposal crashed')
        return _blocked([f'unexpected error: {e}'])
