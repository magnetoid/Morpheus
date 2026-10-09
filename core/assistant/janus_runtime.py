"""Which Janus Linda runs, and keeping it current from its GitHub repository.

The image installs Janus from git at build time (Dockerfile: ``JANUS_REF``,
``main`` by default) and checks it against Morpheus's contract
(:mod:`core.assistant.janus_contract`). Janus moves faster than Morpheus deploys,
so while the image tracks a branch, the store also keeps up by itself:

* every :data:`CHECK_EVERY_S`, a Linda turn or a visit to the Janus page starts
  :mod:`core.assistant.janus_updater` as a detached process. It asks GitHub for
  the branch's newest commit, installs it into a fresh venv beside the current
  one (no git in the image: pip takes GitHub's archive of that commit), runs the
  contract with it, and only then records it as the Janus to use;
* :func:`active_bin` points the engine at that venv. The image's Janus stays as
  the fallback, and nothing else changes for a running conversation;
* :func:`record_turn` watches real turns: three engine failures in a row on an
  auto-installed Janus put the previous one back and mark that commit failed.

Everything lives in the engine dir under the Janus home: a temp dir per
container, so a redeploy starts again from the image (which installs the newest
commit anyway). No volume, no database (the owner's rule for Janus state).

The repository and branch come from the image's own build record, never from the
dashboard: anything the merchant (or Linda, through a settings tool) can edit
must not choose which code the server installs. A build pinned to a commit is a
decision to freeze, so it is never auto-updated.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger('morpheus.assistant.janus')

CHECK_EVERY_S = 3 * 3600
ROLLBACK_AFTER = 3
# Installed alongside Janus, exactly as the Dockerfile pins them.
PINS = ('ddgs==9.16.0', 'primp==2.0.1')
UPDATER = Path(__file__).resolve().with_name('janus_updater.py')
CONTRACT = Path(__file__).resolve().with_name('janus_contract.py')
BUILD_FILE = 'morpheus-build.json'
CONTRACT_FILE = 'morpheus-contract.json'

_GITHUB = re.compile(r'^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$')
_ARCHIVE = re.compile(r'^https://github\.com/([\w.-]+)/([\w.-]+)/archive/([0-9a-f]{40})\.tar\.gz$')
_SHA = re.compile(r'^[0-9a-f]{40}$')
# Engine failures that say nothing about the Janus build itself.
_NOT_THE_BUILD = (
    'timed out',
    '401',
    '402',
    '429',
    'rate',
    'quota',
    'insufficient',
    'unauthorized',
    'api_key',
    'authentication',
)


def _settings():
    from django.conf import settings

    return settings


def engine_dir() -> Path:
    from core.assistant.janus_engine import linda_janus_home

    return linda_janus_home() / 'engine'


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data, indent=1), encoding='utf-8')
    os.replace(tmp, path)


def state() -> dict:
    with contextlib.suppress(OSError):
        return _read_json(engine_dir() / 'state.json')
    return {}


# ── The installed builds ─────────────────────────────────────────────────────


def venv_of(janus_bin: str | None) -> Path | None:
    """The venv a ``janus`` executable belongs to (follows the /usr/local/bin link)."""
    if not janus_bin:
        return None
    exe = shutil.which(janus_bin) or janus_bin
    return Path(os.path.realpath(exe)).parent.parent


def installed_build(janus_bin: str | None) -> dict:
    """Version, commit, ref and repository of a Janus install; '' where unknown.

    An auto-installed venv carries ``morpheus-build.json`` (the updater wrote it);
    the image's carries pip's ``direct_url.json`` from the git install.
    """
    build = {'version': '', 'commit': '', 'ref': '', 'repo': '', 'url': '', 'source': ''}
    venv = venv_of(janus_bin)
    if venv is None:
        return build
    marker = _read_json(venv / BUILD_FILE)
    for dist in sorted(venv.glob('lib/python*/site-packages/janus_agent-*.dist-info')):
        try:
            meta = (dist / 'METADATA').read_text(encoding='utf-8')
        except OSError:
            continue
        version = re.search(r'^Version:\s*(\S+)', meta, re.M)
        build['version'] = version.group(1) if version else ''
        origin = _read_json(dist / 'direct_url.json')
        url = str(origin.get('url') or '')
        vcs = origin.get('vcs_info') or {}
        archive = _ARCHIVE.match(url)
        if archive:
            build['commit'] = archive.group(3)
            build['repo'] = f'{archive.group(1)}/{archive.group(2)}'
            build['url'] = f'https://github.com/{build["repo"]}.git'
        else:
            build['commit'] = str(vcs.get('commit_id') or '')
            build['url'] = url
            match = _GITHUB.match(url)
            build['repo'] = f'{match.group(1)}/{match.group(2)}' if match else ''
        build['ref'] = str(marker.get('ref') or vcs.get('requested_revision') or '')
        break
    build['source'] = 'auto' if marker else 'image'
    return build


def contract_report(janus_bin: str | None) -> dict:
    """The contract report recorded when this Janus was installed, or {}."""
    venv = venv_of(janus_bin)
    return _read_json(venv / CONTRACT_FILE) if venv else {}


def image_bin() -> str | None:
    """The Janus the image installed (``janus`` on PATH), ignoring auto-installs."""
    return shutil.which('janus')


# ── Using an auto-installed Janus ────────────────────────────────────────────


def enabled() -> bool:
    """Deployment switch (``LINDA_JANUS_AUTO_UPDATE``) and the merchant's, both on."""
    if not getattr(_settings(), 'LINDA_JANUS_AUTO_UPDATE', True):
        return False
    from core.assistant import janus_settings

    return janus_settings.auto_update_enabled()


def active_bin() -> str | None:
    """The verified auto-installed ``janus`` to run, or None to use the image's."""
    try:
        if not enabled():
            return None
        root = engine_dir().resolve()
        active = state().get('active') or {}
        path = Path(str(active.get('bin') or '')).resolve()
    except (OSError, RuntimeError):
        return None
    venv = path.parent.parent
    inside = root in path.parents
    commit = str(active.get('commit') or '')
    verified = bool(commit) and _read_json(venv / BUILD_FILE).get('commit') == commit
    if inside and verified and path.is_file() and os.access(path, os.X_OK):
        return str(path)
    return None


def source() -> dict | None:
    """Where updates come from: the image's repository and branch, or None to freeze."""
    build = installed_build(image_bin())
    if not (build['repo'] and build['ref']) or _SHA.match(build['ref']):
        return None
    return {'repo': build['repo'], 'ref': build['ref'], 'image_commit': build['commit']}


def _last_attempt(root: Path) -> float:
    checked = (state().get('last_check') or {}).get('at') or 0
    try:
        spawned = (root / '.last_spawn').stat().st_mtime
    except OSError:
        spawned = 0
    return max(float(checked or 0), spawned)


def maybe_update(*, force: bool = False) -> bool:
    """Start the updater in the background when a check is due. Never blocks."""
    try:
        if not enabled():
            return False
        origin = source()
        if origin is None:
            return False
        root = engine_dir()
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not force and time.time() - _last_attempt(root) < CHECK_EVERY_S:
            return False
        (root / '.last_spawn').touch()
        _spawn_updater(root, origin, force=force)
        return True
    except Exception:  # noqa: BLE001 — an update must never cost a turn
        logger.warning('janus: could not start the updater', exc_info=True)
        return False


def _spawn_updater(root: Path, origin: dict, *, force: bool) -> None:
    argv = [
        sys.executable,
        '-I',
        str(UPDATER),
        '--engine-dir',
        str(root),
        '--repo',
        origin['repo'],
        '--ref',
        origin['ref'],
        '--image-commit',
        origin['image_commit'],
        '--contract',
        str(CONTRACT),
    ]
    for pin in PINS:
        argv += ['--pin', pin]
    if force:
        argv.append('--force')
    env = {
        k: v
        for k, v in os.environ.items()
        if k in ('PATH', 'LANG', 'LC_ALL', 'TZ', 'SSL_CERT_FILE', 'SSL_CERT_DIR')
        or k.lower() in ('http_proxy', 'https_proxy', 'no_proxy')
    }
    env['HOME'] = str(root)
    log = (root / 'updater.log').open('ab')
    proc = subprocess.Popen(  # noqa: S603 — fixed interpreter and script
        argv,
        cwd=str(root),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        start_new_session=True,
        close_fds=True,
    )
    log.close()
    # Reap it when it ends, so a long-lived worker collects no zombies.
    threading.Thread(target=proc.wait, name='janus-updater-reaper', daemon=True).start()
    logger.info('janus: updater started for %s@%s', origin['repo'], origin['ref'])


# ── Health of an auto-installed Janus ────────────────────────────────────────


def record_turn(*, error: str = '') -> None:
    """Count engine failures on an auto-installed Janus; put the previous one back
    after :data:`ROLLBACK_AFTER` in a row."""
    try:
        if active_bin() is None:
            return
        root = engine_dir()
        with _locked(root) as held:
            if not held:
                return  # an update is running; it will settle the state
            current = _read_json(root / 'state.json')
            active = current.get('active') or {}
            failing = bool(error) and not any(n in error.lower() for n in _NOT_THE_BUILD)
            active['failures'] = int(active.get('failures') or 0) + 1 if failing else 0
            current['active'] = active
            if active['failures'] >= ROLLBACK_AFTER:
                _roll_back(current, error)
            _write_json(root / 'state.json', current)
    except Exception:  # noqa: BLE001 — bookkeeping must never fail a turn
        logger.debug('janus: turn health not recorded', exc_info=True)


def _roll_back(current: dict, error: str) -> None:
    active = current.get('active') or {}
    commit = str(active.get('commit') or '')
    current.setdefault('failed', {})[commit] = {
        'at': time.time(),
        'reason': f'{ROLLBACK_AFTER} turns failed in a row: {error[:300]}',
    }
    current['active'] = current.get('previous') or None
    current['previous'] = None
    current['last_check'] = {
        'at': time.time(),
        'result': 'rolled_back',
        'detail': f'Janus {commit[:7]} failed {ROLLBACK_AFTER} turns in a row; went back.',
        'latest': commit,
    }
    logger.warning('janus: rolled back from %s after repeated failures', commit[:12])


@contextlib.contextmanager
def _locked(root: Path):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (root / '.lock').open('a') as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def summary() -> dict[str, Any]:
    """What the Janus page shows about updates."""
    current = state()
    active = active_bin()
    return {
        'enabled': enabled(),
        'source': source(),
        'using': 'auto' if active else 'image',
        'active': current.get('active') if active else None,
        'last_check': current.get('last_check') or None,
        'failed': current.get('failed') or {},
        'every_hours': CHECK_EVERY_S // 3600,
    }
