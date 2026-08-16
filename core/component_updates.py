"""Per-app / per-theme updates — the second unit of update after the platform.

`core/updates.py` fast-forwards the *whole* platform. This module updates ONE
component — an app or a theme installed on its own — from a signed manifest
entry (`core/update_sources.py:ComponentRelease`), without touching anything
else. It is what lets a merchant take a fix to a commercial app or a
third-party theme without redeploying the platform.

What "installed on its own" means, and why the engine refuses the rest
--------------------------------------------------------------------
An app listed in `MORPHEUS_DEFAULT_APPS`, or any component whose directory
is tracked by the deployment's git checkout, ships *with core* and is
versioned by `MORPHEUS_VERSION`. Overwriting it here would fork the tree
from the platform channel: the next core fast-forward would conflict, and
the merchant would run a component core was never tested with. So those are
refused with a reason that says "update core instead". The channel is for
everything else — apps wired in through `MORPHEUS_EXTRA_APPS`, themes dropped
into the themes directory.

Integrity, in order
-------------------
1. The manifest is Ed25519-verified before any entry is believed
   (`SignedManifestSource`); the signature covers each entry's `sha256`.
2. The artifact is streamed over HTTPS with a size cap and hashed as it
   lands; a hash that does not match the signed entry is deleted and refused.
   **A checksum is required** — an entry without one is not applied.
3. The archive is inspected member by member before extraction: absolute
   paths, `..`, links and device nodes are refused, and everything must sit
   under one top-level directory. Extraction then uses `tarfile`'s `data`
   filter as a second line.
4. The extracted tree must look like the component it claims to be (`app.py`
   / `theme.py`), and an app tree with a `migrations/` dir must carry
   `migrations/__init__.py` — a migrations package Django cannot see is the
   landmine that once left five plugins without tables on prod.

Only then does the swap happen — atomic renames, boot probe of the new tree
in a fresh interpreter, `migrate`, `check`, and a rename-back on any failure.
Same posture as the platform apply: dry-run by default, opt-in via
`MORPHEUS_SELF_UPDATE_ENABLED`, and it never leaves the tree half-swapped.

The running process still holds the *old* modules after a successful apply;
the result says so (`restart_required`). This module never restarts anything.
"""

# ruff: noqa: PLC0415
# Inline imports keep this importable before the app registry is ready.

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from core.update_sources import (
    _USER_AGENT,
    COMPONENT_KINDS,
    ComponentRelease,
    _ssl_context,
    configured_source,
    is_newer,
)

logger = logging.getLogger('morpheus.updates')

_MAX_ARTIFACT_BYTES = 256 * 1024 * 1024  # a theme with imagery, comfortably
_MAX_EXTRACTED_BYTES = 1024 * 1024 * 1024  # decompression-bomb ceiling
_FETCH_TIMEOUT = 60  # seconds per read; artifacts are larger than manifests
_CHUNK = 1024 * 256

_MARKER_FILE = {'app': 'app.py', 'theme': 'theme.py'}


class ArtifactError(Exception):
    """The artifact could not be trusted or unpacked. Never leaves files behind."""


# ── Fetch + verify ─────────────────────────────────────────────────────────────


def fetch_artifact(
    url: str, sha256: str, dest_dir: Path, *, max_bytes: int = _MAX_ARTIFACT_BYTES
) -> Path:
    """Download `url` into `dest_dir` and return the path — only if its SHA-256
    equals `sha256`. On any failure the partial file is removed and
    `ArtifactError` is raised.

    The hash is required, not optional: it is what the manifest signature
    binds the bytes to. An entry without one is refused here rather than
    trusted on the strength of HTTPS alone.
    """
    url = (url or '').strip()
    expected = (sha256 or '').strip().lower()
    if not url.lower().startswith('https://'):
        raise ArtifactError('artifact URL must be https://')
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ArtifactError('manifest entry carries no usable sha256 — refusing to fetch')

    dest_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix='artifact-', suffix='.tar.gz', dir=str(dest_dir))
    tmp = Path(tmp_name)
    digest = hashlib.sha256()
    received = 0
    try:
        req = urllib.request.Request(url, headers={'User-Agent': _USER_AGENT})  # noqa: S310
        with (
            os.fdopen(fd, 'wb') as out,
            urllib.request.urlopen(  # noqa: S310 — https enforced above
                req, timeout=_FETCH_TIMEOUT, context=_ssl_context()
            ) as resp,
        ):
            while True:
                chunk = resp.read(_CHUNK)
                if not chunk:
                    break
                received += len(chunk)
                if received > max_bytes:
                    raise ArtifactError(f'artifact exceeds {max_bytes} bytes')
                digest.update(chunk)
                out.write(chunk)
    except ArtifactError:
        tmp.unlink(missing_ok=True)
        raise
    except Exception as exc:  # noqa: BLE001 — network/TLS/DNS: refuse, never partial
        tmp.unlink(missing_ok=True)
        raise ArtifactError(f'download failed: {exc}') from exc

    actual = digest.hexdigest()
    if actual != expected:
        tmp.unlink(missing_ok=True)
        logger.error(
            'updates: artifact %s hashed %s, manifest says %s — refusing', url, actual, expected
        )
        raise ArtifactError('artifact checksum does not match the signed manifest')
    return tmp


# ── Inspect + extract ──────────────────────────────────────────────────────────


def _member_top(name: str) -> str:
    return name.replace('\\', '/').strip('/').split('/', 1)[0]


def inspect_archive(archive: Path) -> str:
    """Validate every member and return the single top-level directory name.

    Raises `ArtifactError` for anything an app or theme tree has no business
    containing: absolute paths, `..`, symlinks or hardlinks, device nodes and
    fifos, more than one top-level entry, or a decompressed size past the
    ceiling. This runs *before* extraction, so a hostile archive touches
    nothing.
    """
    try:
        with tarfile.open(archive, mode='r:gz') as tf:
            members = tf.getmembers()
    except Exception as exc:  # noqa: BLE001
        raise ArtifactError(f'not a gzip tarball: {exc}') from exc
    if not members:
        raise ArtifactError('archive is empty')

    tops: set[str] = set()
    total = 0
    for m in members:
        name = m.name.replace('\\', '/')
        if name.startswith('/') or name.startswith('../') or '/../' in f'/{name}/':
            raise ArtifactError(f'unsafe path in archive: {m.name!r}')
        if m.issym() or m.islnk():
            raise ArtifactError(f'links are not allowed in a component archive: {m.name!r}')
        if m.isdev() or m.isfifo():
            raise ArtifactError(f'special file in archive: {m.name!r}')
        if not (m.isdir() or m.isfile()):
            raise ArtifactError(f'unsupported member type: {m.name!r}')
        total += m.size
        if total > _MAX_EXTRACTED_BYTES:
            raise ArtifactError('archive decompresses past the size ceiling')
        top = _member_top(name)
        if not top or top in ('.', '..'):
            raise ArtifactError(f'unsafe path in archive: {m.name!r}')
        tops.add(top)
    # Every member's first path component is in `tops`, so one entry here
    # means everything sits under one directory — a loose file at the root
    # or a second directory shows up as a second entry.
    if len(tops) != 1:
        raise ArtifactError(
            f'archive must contain exactly one top-level directory (found {sorted(tops)[:5]!r})'
        )
    return next(iter(tops))


def extract_component(archive: Path, staging: Path, kind: str, name: str) -> Path:
    """Unpack `archive` to `staging/<name>` and return that path.

    Accepts any single top-level directory name (`name/` or `name-1.2.0/`, as
    `git archive` produces) and normalises it to `<name>`. Then checks the
    tree looks like a `kind`: the marker file exists, and an app's
    `migrations/` (if any) is a package.
    """
    top = inspect_archive(archive)
    staging.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode='r:gz') as tf:
        # `filter='data'` (3.12+) is the second line: refuses absolute paths,
        # `..`, and links escaping the destination even if the scan above
        # somehow missed one; strips setuid/setgid/sticky bits.
        tf.extractall(path=str(staging), filter='data')  # noqa: S202 — inspected + filtered
    extracted = staging / top
    if not extracted.is_dir():
        raise ArtifactError('archive did not produce the expected directory')
    target = staging / name
    if extracted != target:
        if target.exists():
            shutil.rmtree(target)
        extracted.rename(target)

    marker = _MARKER_FILE[kind]
    if not (target / marker).is_file():
        raise ArtifactError(f'archive is not a {kind}: no {marker} at its root')
    if kind == 'app':
        migrations = target / 'migrations'
        if migrations.is_dir() and not (migrations / '__init__.py').is_file():
            raise ArtifactError(
                'app ships a migrations/ directory without __init__.py — Django would '
                'never see its migrations and its tables would never be created'
            )
    return target


# ── Locate + gate ──────────────────────────────────────────────────────────────


def _repo_root() -> Path:
    from django.conf import settings

    return Path(getattr(settings, 'BASE_DIR', '.')).resolve()


def component_dir(kind: str, name: str) -> Path | None:
    """Directory of the installed component, resolved from the loaded module —
    the one place that is right for in-tree and out-of-tree alike."""
    try:
        if kind == 'app':
            from plugins.registry import app_registry

            cls = app_registry._classes.get(name)  # noqa: SLF001
            if cls is None:
                return None
            import importlib

            mod = importlib.import_module(cls.__module__)
        else:
            from themes.registry import theme_registry

            theme = theme_registry.get(name)
            if theme is None:
                return None
            import sys

            mod = sys.modules.get(type(theme).__module__)
        file = getattr(mod, '__file__', None)
        return Path(file).resolve().parent if file else None
    except Exception:  # noqa: BLE001 — resolution must never break the caller
        return None


def _ships_with_core(kind: str, name: str, path: Path) -> str | None:
    """Reason this component must be updated *with core*, or None if it may be
    updated on its own."""
    from django.conf import settings

    from core.updates import _git_ok

    if kind == 'app':
        try:
            from plugins.registry import app_registry

            cls = app_registry._classes.get(name)  # noqa: SLF001
            module_path = (cls.__module__ if cls else '').rsplit('.', 1)[0]
        except Exception:  # noqa: BLE001
            module_path = ''
        if module_path and module_path in tuple(getattr(settings, 'MORPHEUS_DEFAULT_APPS', ())):
            return 'this app ships with the platform — it is updated with core, not on its own'

    root = _repo_root()
    if (root / '.git').exists():
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = None
        if rel is not None and _git_ok(['ls-files', '--error-unmatch', str(rel)], root):
            return 'this directory is tracked by the deployment git checkout — update core instead'
    return None


def _protected(path: Path) -> bool:
    """Everything that mutates installed code consults `core/safety.py`."""
    from core.safety import is_path_protected

    root = _repo_root()
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return False
    return is_path_protected(rel + '/')


def find_component_release(kind: str, name: str) -> ComponentRelease | None:
    source = configured_source()
    if source is None:
        return None
    return next((r for r in source.components() if r.kind == kind and r.name == name), None)


# ── Apply ──────────────────────────────────────────────────────────────────────


def apply_component_update(  # noqa: PLR0911, PLR0912, PLR0915 — a guarded ladder, on purpose
    kind: str, name: str, *, confirm: bool = False, run_migrations: bool = True
) -> dict:
    """Update one app or theme from the signed manifest. Dry-run by default.

    Status vocabulary (mirrors `apply_platform_update`): `unavailable` (no
    source / no entry / not installed), `noop`, `dry_run`, `disabled`,
    `blocked` (ships with core, protected path, core too old), `verify_failed`
    (checksum / archive), `apply_failed`, `rolled_back`, `applied`.
    """
    from django.conf import settings

    if kind not in COMPONENT_KINDS:
        return {'ok': False, 'status': 'unavailable', 'reason': f'unknown component kind {kind!r}'}

    from core.update_sources import installed_components
    from core.versioning import core_version

    current = installed_components().get((kind, name))
    if current is None:
        return {
            'ok': False,
            'status': 'unavailable',
            'reason': f'{kind} {name!r} is not installed here.',
        }
    release = find_component_release(kind, name)
    if release is None:
        return {
            'ok': False,
            'status': 'unavailable',
            'reason': f'The update source publishes no entry for {kind} {name!r}.',
        }
    if not is_newer(release.version, current):
        return {
            'ok': True,
            'status': 'noop',
            'message': f'{name} {current} is already current.',
            'current': current,
        }

    plan = {'kind': kind, 'name': name, 'from': current, 'to': release.version}
    if release.min_core and is_newer(release.min_core, core_version()):
        return {
            'ok': False,
            'status': 'blocked',
            'plan': plan,
            'reason': (
                f'{name} {release.version} needs core {release.min_core} or newer '
                f'(running {core_version()}). Update the platform first.'
            ),
        }
    target = component_dir(kind, name)
    if target is None or not target.is_dir():
        return {
            'ok': False,
            'status': 'unavailable',
            'plan': plan,
            'reason': f'Could not locate the installed directory of {kind} {name!r}.',
        }
    reason = _ships_with_core(kind, name, target)
    if reason:
        return {'ok': False, 'status': 'blocked', 'plan': plan, 'reason': reason}
    if _protected(target):
        return {
            'ok': False,
            'status': 'blocked',
            'plan': plan,
            'reason': f'{target} is inside a protected path (core/safety.py).',
        }
    if not release.sha256:
        return {
            'ok': False,
            'status': 'verify_failed',
            'plan': plan,
            'reason': 'The manifest entry carries no sha256; refusing an unverifiable artifact.',
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

    from django.core.management import call_command

    from core.updates import _boot_probe

    try:
        call_command('morph_backup')
    except Exception:  # noqa: BLE001 — proceed even if backup is unavailable, but note it
        plan['backup'] = 'failed'

    parent = target.parent
    staging = parent / f'.morpheus-staging-{name}'
    previous = parent / f'.morpheus-previous-{name}'
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(previous, ignore_errors=True)

    try:
        try:
            archive = fetch_artifact(release.artifact, release.sha256, staging)
            new_tree = extract_component(archive, staging / 'unpacked', kind, name)
            archive.unlink(missing_ok=True)
        except ArtifactError as exc:
            return {'ok': False, 'status': 'verify_failed', 'plan': plan, 'reason': str(exc)}

        # Swap: two renames. If the second fails, the first is undone.
        try:
            os.rename(target, previous)
        except OSError as exc:
            return {
                'ok': False,
                'status': 'apply_failed',
                'plan': plan,
                'reason': f'could not move the current tree aside: {exc}',
            }
        try:
            os.rename(new_tree, target)
        except OSError as exc:
            os.rename(previous, target)
            return {
                'ok': False,
                'status': 'apply_failed',
                'plan': plan,
                'reason': f'could not move the new tree into place: {exc}',
            }

        def _rollback(why: str) -> dict:
            shutil.rmtree(target, ignore_errors=True)
            os.rename(previous, target)
            return {'ok': False, 'status': 'rolled_back', 'plan': plan, 'reason': why}

        boot_ok, boot_tail = _boot_probe(_repo_root())
        if not boot_ok:
            return _rollback(
                f'new {kind} failed to boot ({boot_tail[:160]}); previous tree restored.'
            )
        if kind == 'app' and run_migrations:
            try:
                call_command('migrate', '--noinput')
            except Exception as exc:  # noqa: BLE001
                return _rollback(
                    f'migrate failed ({str(exc)[:160]}); previous tree restored. '
                    'REVIEW DB — restore the pre-update backup if needed.'
                )
        try:
            call_command('check')
        except Exception as exc:  # noqa: BLE001
            return _rollback(f'post-update healthcheck failed ({str(exc)[:160]}).')

        shutil.rmtree(previous, ignore_errors=True)
        return {
            'ok': True,
            'status': 'applied',
            'plan': plan,
            'from': current,
            'to': release.version,
            'restart_required': True,
            'message': (
                f'{name} updated {current} → {release.version}. Restart the process to load it.'
            ),
        }
    finally:
        shutil.rmtree(staging, ignore_errors=True)
