"""Install the newest Janus from GitHub beside the current one, if it keeps the contract.

Started in the background by :func:`core.assistant.janus_runtime.maybe_update`
(never in a request), with the store's own Python::

    python -I janus_updater.py --engine-dir DIR --repo OWNER/NAME --ref main \\
        --image-commit SHA --contract PATH [--pin PKG==VER ...] [--force]

1. One run per container at a time (an exclusive lock on ``DIR/.lock``).
2. Ask GitHub for the newest commit on the branch. Nothing newer: done.
3. A commit that already failed is not retried (``--force`` retries it).
4. ``python -m venv DIR/venvs/<sha12>`` and pip install GitHub's archive of
   exactly that commit (the image has no git), plus the pinned extras.
5. Run the contract with the new venv's Python. Any required check failing
   means the commit is recorded as failed and the venv is deleted.
6. Otherwise write ``morpheus-build.json`` and ``morpheus-contract.json`` into
   the venv and record it in ``DIR/state.json`` as the Janus to use; the one it
   replaces is kept as ``previous`` for a rollback, older venvs are deleted.

Standard library only: it runs without Django, from a fixed path in the image.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

_SHA = re.compile(r'^[0-9a-f]{40}$')
_REPO = re.compile(r'^[\w.-]+/[\w.-]+$')
_REF = re.compile(r'^[\w./-]{1,100}$')
INSTALL_TIMEOUT_S = 900
CONTRACT_TIMEOUT_S = 300


def _now() -> float:
    return time.time()


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict) -> None:
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data, indent=1), encoding='utf-8')
    os.replace(tmp, path)


def latest_commit(repo: str, ref: str) -> dict:
    """``{sha, title, date}`` of the newest commit on ``ref``. Raises on failure."""
    request = Request(  # noqa: S310 — fixed https host
        f'https://api.github.com/repos/{repo}/commits/{ref}',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'morpheus-janus-updater'},
    )
    with urlopen(request, timeout=20) as resp:  # noqa: S310
        data = json.loads(resp.read().decode('utf-8'))
    sha = str(data.get('sha') or '')
    if not _SHA.match(sha):
        raise ValueError(f'GitHub answered without a commit for {repo}@{ref}')
    commit = data.get('commit') or {}
    return {
        'sha': sha,
        'title': str(commit.get('message') or '').split('\n', 1)[0][:160],
        'date': str((commit.get('committer') or {}).get('date') or '')[:10],
    }


def _env(home: Path) -> dict:
    keep = ('PATH', 'LANG', 'LC_ALL', 'TZ', 'SSL_CERT_FILE', 'SSL_CERT_DIR')
    env = {k: v for k, v in os.environ.items() if k in keep or k.lower().endswith('_proxy')}
    env.update({'HOME': str(home), 'JANUS_HOME': str(home), 'PIP_DISABLE_PIP_VERSION_CHECK': '1'})
    return env


def install(venv: Path, repo: str, sha: str, pins: list[str], home: Path) -> tuple[bool, str]:
    """A fresh venv with Janus at ``sha``. Returns (ok, the tail of pip's output)."""
    shutil.rmtree(venv, ignore_errors=True)
    venv.parent.mkdir(parents=True, exist_ok=True)
    package = f'janus-agent[mcp] @ https://github.com/{repo}/archive/{sha}.tar.gz'
    steps = (
        [sys.executable, '-m', 'venv', str(venv)],
        [str(venv / 'bin' / 'pip'), 'install', '--no-cache-dir', '-q', package, *pins],
    )
    for argv in steps:
        try:
            proc = subprocess.run(  # noqa: S603 — fixed interpreter, validated repo and sha
                argv,
                capture_output=True,
                text=True,
                timeout=INSTALL_TIMEOUT_S,
                env=_env(home),
                cwd=str(home),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as e:
            return False, str(e)[:500]
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout or '')[-500:]
    return True, ''


def run_contract(venv: Path, contract: Path, home: Path) -> dict:
    """The contract report for the Janus in ``venv`` (``ok`` False when it can't run)."""
    try:
        proc = subprocess.run(  # noqa: S603 — the new venv's Python, our script
            [str(venv / 'bin' / 'python'), '-I', str(contract)],
            capture_output=True,
            text=True,
            timeout=CONTRACT_TIMEOUT_S,
            env=_env(home),
            cwd=str(home),
            check=False,
        )
        report = json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        return {'ok': False, 'checks': [], 'error': str(e)[:300]}
    return report if isinstance(report, dict) else {'ok': False, 'checks': []}


def _failed_checks(report: dict) -> str:
    names = [
        c.get('name', '?')
        for c in report.get('checks') or []
        if c.get('required') and not c.get('ok')
    ]
    return ', '.join(names) or str(report.get('error') or 'the contract did not run')


def _prune(root: Path, keep: set[str]) -> None:
    venvs = root / 'venvs'
    if not venvs.is_dir():
        return
    for child in venvs.iterdir():
        if child.name not in keep:
            shutil.rmtree(child, ignore_errors=True)


@contextlib.contextmanager
def _lock(root: Path):
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


def update(args: argparse.Namespace) -> str:
    """One check. Returns the result recorded in ``state.json['last_check']``."""
    root = Path(args.engine_dir)
    state = _read(root / 'state.json')
    failed = state.setdefault('failed', {})

    def record(result: str, detail: str = '', latest: str = '') -> str:
        state['last_check'] = {'at': _now(), 'result': result, 'detail': detail, 'latest': latest}
        _write(root / 'state.json', state)
        print(f'janus-updater: {result} {latest[:12]} {detail}'.rstrip(), flush=True)
        return result

    try:
        latest = latest_commit(args.repo, args.ref)
    except Exception as e:  # noqa: BLE001 — recorded and shown, retried on the next check
        return record('error', f'GitHub: {str(e)[:300]}')
    sha = latest['sha']
    current = str((state.get('active') or {}).get('commit') or args.image_commit or '')
    if sha == current:
        return record('current', '', sha)
    if sha in failed and not args.force:
        return record('skipped', 'this commit failed before', sha)

    venv = root / 'venvs' / sha[:12]
    ok, detail = install(venv, args.repo, sha, list(args.pin or []), root)
    if not ok:
        shutil.rmtree(venv, ignore_errors=True)
        failed[sha] = {'at': _now(), 'reason': f'install failed: {detail}'}
        return record('failed', f'install failed: {detail[-200:]}', sha)
    report = run_contract(venv, Path(args.contract), root)
    if not report.get('ok'):
        shutil.rmtree(venv, ignore_errors=True)
        failed[sha] = {'at': _now(), 'reason': f'contract: {_failed_checks(report)}'}
        return record('failed', f'contract: {_failed_checks(report)}', sha)

    build = {'commit': sha, 'repo': args.repo, 'ref': args.ref, **latest, 'installed_at': _now()}
    _write(venv / 'morpheus-contract.json', report)
    _write(venv / 'morpheus-build.json', build)
    if state.get('active'):
        state['previous'] = state['active']
    state['active'] = {
        'commit': sha,
        'version': str(report.get('version') or ''),
        'bin': str(venv / 'bin' / 'janus'),
        'installed_at': _now(),
        'title': latest['title'],
        'date': latest['date'],
        'failures': 0,
    }
    failed.pop(sha, None)
    result = record('installed', latest['title'], sha)
    keep = {sha[:12]}
    if state.get('previous'):
        keep.add(str(state['previous'].get('commit') or '')[:12])
    _prune(root, keep)
    return result


def _args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    parser.add_argument('--engine-dir', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--ref', required=True)
    parser.add_argument('--image-commit', default='')
    parser.add_argument('--contract', required=True)
    parser.add_argument('--pin', action='append')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)
    if not _REPO.match(args.repo) or not _REF.match(args.ref):
        parser.error('repo must be owner/name and ref a branch name')
    for pin in args.pin or []:
        if not re.match(r'^[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+$', pin):
            parser.error(f'pin {pin!r} must be NAME==VERSION')
    return args


def main(argv: list[str] | None = None) -> int:
    args = _args(sys.argv[1:] if argv is None else argv)
    root = Path(args.engine_dir)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with _lock(root) as held:
        if not held:
            print('janus-updater: another update is running', flush=True)
            return 0
        result = update(args)
    return 0 if result in ('current', 'installed', 'skipped') else 1


if __name__ == '__main__':
    sys.exit(main())
