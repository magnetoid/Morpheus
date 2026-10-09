"""One-command version release — the writer side of the versioning system.

`morph_versions` reads the version inventory; this command *bumps* it. A
production deploy must bump `MORPHEUS_VERSION` and add a matching dated
`docs/RELEASE_NOTES.md` entry (ADR 0032/0033) — two hand edits that were easy
to forget or desync, and a miss only surfaced *after* deploy as a failed
`/readyz` smoke. This does both atomically and can *verify* them pre-push.

Bump + write notes:

    python manage.py release --minor "Default image settings" \\
        -m "Merchants can set fallback product + OG images" \\
        -m "Falls back to the theme placeholder when unset"

    python manage.py release --patch "Fix cart rounding" --commit
    python manage.py release --set v1.0.0 "First stable"

Verify (pre-push / CI — no writes, exits non-zero on a problem):

    python manage.py release --check

The source of truth is unchanged: `MORPHEUS_VERSION` (settings.py default) +
the newest `## vX.Y.Z — YYYY-MM-DD` heading in RELEASE_NOTES.md. Nothing about
prod/Coolify/deploy-smoke changes.
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# A change under these trees is a versioned change (ADR 0033) — app code OR
# theme code. Tests and non-shipping trees (docs, scripts, CI, .torsor) don't
# themselves require a bump.
VERSIONED_PREFIXES = ('core/', 'plugins/installed/', 'morph/', 'themes/')
_EXCLUDED_SUBSTRINGS = ('/tests/',)

_SETTINGS_RE = re.compile(
    r"(MORPHEUS_VERSION\s*=\s*config\(\s*'MORPHEUS_VERSION'\s*,\s*default\s*=\s*')"
    r'(v\d+\.\d+\.\d+)'
    r"(')"
)
_SEMVER_RE = re.compile(r'^v(\d+)\.(\d+)\.(\d+)$')
# Newest release heading, e.g. "## v0.24.0 — 2026-07-19" (em dash or hyphen).
_HEADING_RE = re.compile(r'^##\s+(v\d+\.\d+\.\d+)\s*[—\-–]\s*(\d{4}-\d{2}-\d{2})\s*$', re.MULTILINE)


def _base_dir() -> Path:
    return Path(settings.BASE_DIR)


def _settings_path() -> Path:
    return _base_dir() / 'morph' / 'settings.py'


def _notes_path() -> Path:
    return _base_dir() / 'docs' / 'RELEASE_NOTES.md'


def parse_current_version(settings_text: str) -> str:
    """Return the `vX.Y.Z` currently declared as the MORPHEUS_VERSION default."""
    m = _SETTINGS_RE.search(settings_text)
    if not m:
        raise CommandError('Could not find the MORPHEUS_VERSION default in morph/settings.py')
    return m.group(2)


def bump(version: str, level: str) -> str:
    """Return the next version. `level` is 'major' | 'minor' | 'patch'."""
    m = _SEMVER_RE.match(version)
    if not m:
        raise CommandError(f'Not a vMAJOR.MINOR.PATCH version: {version!r}')
    major, minor, patch = (int(g) for g in m.groups())
    if level == 'major':
        major, minor, patch = major + 1, 0, 0
    elif level == 'minor':
        minor, patch = minor + 1, 0
    elif level == 'patch':
        patch += 1
    else:  # pragma: no cover — argparse constrains the choices
        raise CommandError(f'Unknown bump level: {level!r}')
    return f'v{major}.{minor}.{patch}'


def newest_notes_version(notes_text: str) -> tuple[str, str] | None:
    """Return (version, date) of the newest release heading, or None."""
    m = _HEADING_RE.search(notes_text)
    return (m.group(1), m.group(2)) if m else None


def render_entry(version: str, date: str, summary: str, bullets: list[str]) -> str:
    """Render one RELEASE_NOTES card, newest-first, with a trailing blank line."""
    lines = [f'## {version} — {date}', '', f'**{summary}**']
    if bullets:
        lines.append('')
        lines.extend(f'- {b}' for b in bullets)
    # Exactly one trailing newline — insert_entry adds the blank-line separator,
    # so appending a blank here would double it between release cards.
    return '\n'.join(lines) + '\n'


def insert_entry(notes_text: str, entry: str) -> str:
    """Insert `entry` as the newest card — right after the intro `---` rule."""
    marker = '\n---\n'
    idx = notes_text.find(marker)
    if idx == -1:
        raise CommandError("docs/RELEASE_NOTES.md is missing its intro '---' separator")
    cut = idx + len(marker)
    head, tail = notes_text[:cut], notes_text[cut:]
    return f'{head}\n{entry}\n{tail.lstrip(chr(10))}'


def set_settings_version(settings_text: str, new_version: str) -> str:
    """Return settings.py text with the MORPHEUS_VERSION default replaced."""
    return _SETTINGS_RE.sub(rf'\g<1>{new_version}\g<3>', settings_text, count=1)


def extract_section(notes_text: str, version: str) -> str:
    """Return one version's notes body (heading excluded), for a GitHub Release.

    Spans from that `## vX.Y.Z` heading to the next `## ` (or EOF). The
    release-tagging workflow feeds this to `gh release create --notes-file`.
    """
    pattern = re.compile(
        rf'^##\s+{re.escape(version)}\b.*?$(.*?)(?=^##\s|\Z)',
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(notes_text)
    if not m:
        raise CommandError(f'No RELEASE_NOTES section for {version}.')
    return m.group(1).strip() + '\n'


# ---------------------------------------------------------------------------
# --check helpers (git-aware; fail-soft when git is unavailable)
# ---------------------------------------------------------------------------


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603 — fixed argv, no shell, repo-root cwd
            ['git', *args],  # noqa: S607
            cwd=_base_dir(),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def _resolves(ref: str) -> bool:
    return _git('rev-parse', '--verify', '--quiet', f'{ref}^{{commit}}') is not None


def _diff_base() -> str | None:
    """The ref to diff HEAD against.

    ``RELEASE_CHECK_BASE`` wins when it names a real commit — CI sets it to the
    push's ``before`` SHA. Otherwise the merge-base with origin/main (a PR or
    feature branch). When that merge-base IS HEAD — i.e. we are on main itself,
    which is exactly where a direct push lands — diffing HEAD against itself
    finds nothing, so a push that skipped the bump passed the check and shipped
    unversioned (v0.83.4 → 02f239f). Fall back to the parent commit there.
    """
    explicit = os.environ.get('RELEASE_CHECK_BASE', '').strip()
    if explicit and set(explicit) != {'0'} and _resolves(explicit):
        return explicit
    if _git('rev-parse', '--verify', '--quiet', 'origin/main') is None:
        return None
    mb = (_git('merge-base', 'origin/main', 'HEAD') or '').strip()
    head = (_git('rev-parse', 'HEAD') or '').strip()
    if mb and mb == head:
        return 'HEAD~1' if _resolves('HEAD~1') else None
    return mb or 'origin/main'


def versioned_changes(changed_paths: list[str]) -> list[str]:
    """Filter a changed-file list down to the ones that require a bump."""
    out = []
    for p in changed_paths:
        if any(sub in p for sub in _EXCLUDED_SUBSTRINGS):
            continue
        if p.startswith(VERSIONED_PREFIXES):
            out.append(p)
    return out


class Command(BaseCommand):
    help = 'Bump MORPHEUS_VERSION + add a dated RELEASE_NOTES entry (or --check both).'

    def add_arguments(self, parser) -> None:
        level = parser.add_mutually_exclusive_group()
        level.add_argument('--major', action='store_const', const='major', dest='level')
        level.add_argument('--minor', action='store_const', const='minor', dest='level')
        level.add_argument('--patch', action='store_const', const='patch', dest='level')
        parser.add_argument('--set', dest='explicit', help='Set an explicit vX.Y.Z (escape hatch).')
        parser.add_argument('summary', nargs='?', help='One-line headline for the notes entry.')
        parser.add_argument(
            '-m',
            '--message',
            action='append',
            default=[],
            dest='bullets',
            help='A bullet line (repeatable).',
        )
        parser.add_argument('--check', action='store_true', help='Verify only; write nothing.')
        parser.add_argument('--commit', action='store_true', help='git commit the two files.')
        parser.add_argument(
            '--show',
            metavar='vX.Y.Z',
            help="Print one version's notes body (for gh release --notes-file) and exit.",
        )

    def handle(self, *args, **opts) -> None:
        if opts['show']:
            notes_text = _notes_path().read_text(encoding='utf-8')
            self.stdout.write(extract_section(notes_text, opts['show']), ending='')
            return
        if opts['check']:
            self._check()
            return
        self._release(opts)

    # ------------------------------------------------------------------

    def _release(self, opts) -> None:
        level, explicit, summary = opts['level'], opts['explicit'], opts['summary']
        if not (level or explicit):
            raise CommandError('Pass a bump level (--patch/--minor/--major) or --set vX.Y.Z.')
        if not summary:
            raise CommandError('A one-line summary is required (positional arg).')

        settings_path, notes_path = _settings_path(), _notes_path()
        settings_text = settings_path.read_text(encoding='utf-8')
        notes_text = notes_path.read_text(encoding='utf-8')

        current = parse_current_version(settings_text)
        if explicit:
            if not _SEMVER_RE.match(explicit):
                raise CommandError(f'--set expects vMAJOR.MINOR.PATCH, got {explicit!r}')
            new_version = explicit
        else:
            new_version = bump(current, level)

        newest = newest_notes_version(notes_text)
        if newest and newest[0] == new_version:
            raise CommandError(f'{new_version} already has a RELEASE_NOTES entry.')

        today = datetime.date.today().isoformat()
        entry = render_entry(new_version, today, summary, opts['bullets'])

        settings_path.write_text(set_settings_version(settings_text, new_version), encoding='utf-8')
        notes_path.write_text(insert_entry(notes_text, entry), encoding='utf-8')

        self.stdout.write(self.style.MIGRATE_HEADING(f'{current} -> {new_version}'))
        self.stdout.write(self.style.SUCCESS('  ✓ morph/settings.py       MORPHEUS_VERSION'))
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ docs/RELEASE_NOTES.md   ## {new_version} — {today}')
        )

        rel = ['morph/settings.py', 'docs/RELEASE_NOTES.md']
        if _git('add', *rel) is not None:
            self.stdout.write(self.style.SUCCESS('  ✓ staged both files'))
        if opts['commit']:
            msg = f'chore(release): {new_version} — {summary}'
            if _git('commit', '-m', msg) is not None:
                self.stdout.write(self.style.SUCCESS(f'  ✓ committed: {msg}'))

    # ------------------------------------------------------------------

    def _check(self) -> None:
        settings_text = _settings_path().read_text(encoding='utf-8')
        notes_text = _notes_path().read_text(encoding='utf-8')

        current = parse_current_version(settings_text)
        newest = newest_notes_version(notes_text)

        problems: list[str] = []
        if newest is None:
            problems.append('RELEASE_NOTES.md has no `## vX.Y.Z — YYYY-MM-DD` heading.')
        elif newest[0] != current:
            problems.append(
                f'Out of sync: MORPHEUS_VERSION is {current} but the newest RELEASE_NOTES '
                f'entry is {newest[0]}. Bump both together (manage.py release).'
            )

        base = _diff_base()
        if base is None:
            self.stdout.write(
                self.style.WARNING('  ! no origin/main to diff — skipped the missing-bump check')
            )
        else:
            names = _git('diff', '--name-only', f'{base}...HEAD') or ''
            changed = versioned_changes([p for p in names.splitlines() if p])
            base_settings = _git('show', f'{base}:morph/settings.py')
            base_version = parse_current_version(base_settings) if base_settings else None
            if changed and base_version is not None and base_version == current:
                sample = ', '.join(changed[:3]) + ('…' if len(changed) > 3 else '')
                problems.append(
                    f'App/theme code changed since {base[:12]} ({sample}) but MORPHEUS_VERSION '
                    f'is still {current}. A deploy MUST bump it (ADR 0033) — run '
                    f'manage.py release --patch/--minor/--major "…".'
                )

        if problems:
            for p in problems:
                self.stderr.write(self.style.ERROR(f'  ✗ {p}'))
            raise CommandError('release --check failed.')
        self.stdout.write(self.style.SUCCESS(f'  ✓ version {current} in sync with RELEASE_NOTES'))
