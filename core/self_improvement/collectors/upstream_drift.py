"""upstream_drift collector — the vibecoding-platform differentiator.

For each tracked file in the repo, compute the diff vs canonical
Morpheus (a fixed git tag or remote ref). Classify each diverged file:

  - **intentional**: a row exists in si_customization (declared by the
    shop owner). Off-limits to every healer except upstream_sync.
  - **drift**: file diverges, no declaration. The dashboard surfaces
    these for the engineer to either declare-intentional or re-merge.
  - **orphan**: only a single hunk diverges and it looks like a one-off
    edit (a typo fix, a colour tweak). Highest-priority for upstream
    sync because the cost of re-merging is tiny.

Phase 1 ships the detection + classification. The actual cherry-pick
healer (class 16, `upstream_sync`) ships in Phase 4.

Configuration sources (checked in order):
  1. settings.SELF_IMPROVEMENT['upstream_ref'] — explicit override
  2. `core/customizations.yml` top-level `upstream:` key
  3. Auto-detect: latest tag matching ``morpheus-*`` on the remote
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

from django.conf import settings

from core.self_improvement.collectors.base import Collector, Signal
from core.self_improvement.services import fingerprint_for, is_path_customized

logger = logging.getLogger('morpheus.self_improvement.upstream_drift')

SOURCE = 'upstream_drift'

# Single-hunk diffs are the easiest re-merges; everything else needs a
# human to classify intentional vs drift before we attempt cherry-pick.
ORPHAN_HUNK_LIMIT = 1
ORPHAN_LINE_LIMIT = 20


class UpstreamDriftCollector(Collector):
    name = SOURCE

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or Path(getattr(settings, 'BASE_DIR', '.'))

    def run(self) -> Iterable[Signal]:
        if shutil.which('git') is None:
            logger.warning('upstream_drift: git not on PATH; skipping')
            return

        upstream_ref = self._resolve_upstream_ref()
        if not upstream_ref:
            logger.warning('upstream_drift: no upstream ref configured or detectable; skipping')
            return

        # `git diff --numstat <upstream>..HEAD` gives one line per file:
        # `<added>\t<removed>\t<path>`. Cheap; doesn't materialise the
        # diff body unless we drill into a specific file.
        try:
            stat_out = self._git(['diff', '--numstat', f'{upstream_ref}..HEAD'])
        except subprocess.CalledProcessError as exc:
            logger.warning(
                'upstream_drift: git diff failed against %s: %s',
                upstream_ref,
                exc.stderr[:300] if exc.stderr else '?',
            )
            return

        for line in stat_out.splitlines():
            parts = line.split('\t')
            if len(parts) != 3:
                continue
            added_str, removed_str, path = parts
            if path.endswith('/'):
                continue  # rename markers etc.
            yield self._signal_for(path, added_str, removed_str, upstream_ref)

    # ------------------------------------------------------------------

    def _signal_for(self, path: str, added_str: str, removed_str: str, upstream_ref: str) -> Signal:
        added = self._int(added_str)
        removed = self._int(removed_str)
        classification = self._classify(path, added, removed, upstream_ref)

        return Signal(
            source=SOURCE,
            fingerprint=fingerprint_for(SOURCE, path, classification),
            severity=self._severity_for(classification),
            payload={
                'path': path,
                'upstream_ref': upstream_ref,
                'classification': classification,
                'added': added,
                'removed': removed,
            },
        )

    def _classify(self, path: str, added: int, removed: int, upstream_ref: str) -> str:
        # Declared in the registry → intentional, period.
        if is_path_customized(path):
            return 'intentional'

        # Tiny diffs are likely orphans (typo fix, missed cherry-pick).
        hunks = self._count_hunks(path, upstream_ref)
        if hunks <= ORPHAN_HUNK_LIMIT and (added + removed) <= ORPHAN_LINE_LIMIT:
            return 'orphan'

        return 'drift'

    def _count_hunks(self, path: str, upstream_ref: str) -> int:
        """Approximate hunk count via unified-diff `@@` headers. Cheap
        enough at our scale; not used for paths we already know are
        intentional (the registry check happens first)."""
        try:
            diff = self._git(['diff', '--unified=0', f'{upstream_ref}..HEAD', '--', path])
        except subprocess.CalledProcessError:
            return 99
        return sum(1 for line in diff.splitlines() if line.startswith('@@'))

    @staticmethod
    def _severity_for(classification: str) -> int:
        return {
            'intentional': 20,  # informational; never actionable
            'orphan': 60,  # cheap re-merge candidate
            'drift': 45,  # needs human classification first
        }.get(classification, 40)

    # ------------------------------------------------------------------

    def _resolve_upstream_ref(self) -> str:
        """Return the git ref representing canonical Morpheus, or '' if
        we can't tell. Checks settings → customizations.yml → auto-detect.
        """
        cfg = getattr(settings, 'SELF_IMPROVEMENT', {}) or {}
        explicit = cfg.get('upstream_ref')
        if explicit:
            return str(explicit)

        from_yml = self._read_customizations_upstream()
        if from_yml:
            return from_yml

        return self._auto_detect_upstream_ref()

    def _read_customizations_upstream(self) -> str:
        path = self.repo_root / 'core' / 'customizations.yml'
        if not path.is_file():
            return ''
        # Tiny YAML parser — we accept a `upstream: <ref>` top-level key,
        # nothing else. Saves a yaml import for one config line.
        try:
            for raw in path.read_text(encoding='utf-8').splitlines():
                stripped = raw.strip()
                if stripped.startswith('upstream:'):
                    return stripped.split(':', 1)[1].strip().strip('"').strip("'")
        except OSError as exc:
            logger.warning('upstream_drift: cannot read customizations.yml: %s', exc)
        return ''

    def _auto_detect_upstream_ref(self) -> str:
        """Find the latest tag matching `morpheus-*`. Returns '' if none
        exist (which is fine — auto-detection is best-effort)."""
        try:
            out = self._git(['tag', '--list', 'morpheus-*', '--sort=-creatordate'])
        except subprocess.CalledProcessError:
            return ''
        for raw in out.splitlines():
            cleaned = raw.strip()
            if cleaned:
                return cleaned
        return ''

    # ------------------------------------------------------------------

    def _git(self, args: list[str]) -> str:
        # `git` resolved via PATH at runtime (Coolify/Docker has git in $PATH);
        # args are static internal lists, never user input.
        cmd = ['git', *args]  # noqa: S607
        proc = subprocess.run(  # noqa: S603 — `cmd` is a static internal list
            cmd,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        return proc.stdout

    @staticmethod
    def _int(s: str) -> int:
        try:
            return int(s)
        except (TypeError, ValueError):
            return 0
