#!/usr/bin/env python3
"""Put a store back on the previous release when a new one leaves it down.

Run by .github/workflows/deploy-smoke.yml after scripts/deploy_smoke.sh fails
(safe deploys, part 3). Standard library only: CI runs it with the system
Python.

A store is put back only when it is down, not when it is late. One that still
serves an older version is queued behind the others, or missed its webhook, and
is left alone. One that answers 503 for a few seconds is being swapped, so each
store is checked CHECKS times, CHECK_GAP seconds apart.

It puts a store back by sending that store's Coolify manual GitHub webhook a
signed push event naming the previous release tag's commit: Coolify deploys the
``after`` commit of a push to the application whose own secret signed it. The
guard holds only those per-store secrets, never an API token: one secret can
deploy commits of this repository to one store, which is what pushing to main
can do anyway. A push deploys its own commit whatever an application is pinned
to, so nothing needs unpinning; but Coolify's Redeploy deploys main, the commit
that failed, until a fix is pushed.

Configuration, the MORPHEUS_DEPLOY_HOOKS secret (JSON):
  {"webhook": "https://<coolify>/webhooks/source/github/events/manual",
   "repository": "<owner>/<repo>", "branch": "main",
   "stores": {"https://store.example": "<that application's manual webhook secret>"}}
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = 3  # a store counts as down only when it fails this many checks in a row
CHECK_GAP = 20  # seconds between them
WAIT = 30 * 60  # how long the stores put back get to come up, together
_VERSION = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
_SETTINGS = re.compile(r"MORPHEUS_VERSION = config\('MORPHEUS_VERSION', default='([^']+)'\)")


def version_key(text: str) -> tuple[int, ...] | None:
    match = _VERSION.match(text.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def expected_version(settings_text: str) -> str:
    match = _SETTINGS.search(settings_text)
    return match.group(1) if match else ''


def previous_release(expected: str, tags: list[str]) -> str | None:
    """The newest release tag older than ``expected``."""
    ceiling = version_key(expected)
    if ceiling is None:
        return None
    older = [tag for tag in tags if (key := version_key(tag)) is not None and key < ceiling]
    return max(older, key=version_key) if older else None


def http_get(url: str, timeout: float = 15) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={'User-Agent': 'morpheus-deploy-guard'})  # noqa: S310 — configured https URLs
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — configured https URLs
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, OSError):
        return 0, ''


def http_post(url: str, body: bytes, headers: dict, timeout: float = 30) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')  # noqa: S310 — the configured webhook
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — the configured webhook
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(exc)


def store_state(base: str, get=http_get) -> tuple[str, bool]:
    """``(version, healthy)``: what /readyz reports, and whether the store works
    as a shop (/readyz ``ok`` and the home page 200)."""
    status, body = get(f'{base}/readyz')
    try:
        data = json.loads(body) if status == 200 else {}
    except ValueError:
        data = {}
    version = str(data.get('version') or '') if isinstance(data, dict) else ''
    if not isinstance(data, dict) or data.get('status') != 'ok':
        return version, False
    home, _ = get(f'{base}/')
    return version, home == 200


def classify(base: str, expected: str, *, get=http_get, sleep=time.sleep) -> str:
    """'up' (healthy on ``expected``), 'late' (healthy on another version) or
    'down' (not healthy at any of CHECKS checks)."""
    for attempt in range(CHECKS):
        version, healthy = store_state(base, get)
        if healthy:
            return 'up' if version == expected else 'late'
        if attempt + 1 < CHECKS:
            sleep(CHECK_GAP)
    return 'down'


def sign(secret: str, body: bytes) -> str:
    return 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def deploy_commit(
    hook: str, repository: str, branch: str, secret: str, commit: str, post=http_post
):
    """Send the store's webhook a signed push event naming ``commit``."""
    body = json.dumps(
        {
            'ref': f'refs/heads/{branch}',
            'after': commit,
            'repository': {'full_name': repository},
            'commits': [],
        }
    ).encode()
    headers = {
        'Content-Type': 'application/json',
        'X-GitHub-Event': 'push',
        'X-Hub-Signature-256': sign(secret, body),
        'User-Agent': 'morpheus-deploy-guard',
    }
    return post(hook, body, headers)


def queued(text: str) -> bool:
    """Whether Coolify's answer says a deployment was queued."""
    try:
        data = json.loads(text)
    except ValueError:
        return False
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if item.get('status') == 'success':
                return True
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return False


def _git(*args: str) -> str:
    cmd = ['git', *args]
    done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)  # noqa: S603
    return done.stdout


def tag_commit(tag: str) -> str:
    return _git('rev-list', '-n', '1', tag).strip()


def release_tags() -> list[str]:
    return _git('tag', '--list', 'v*').split()


def load_config(env=None) -> dict:
    env = os.environ if env is None else env
    raw = (env.get('MORPHEUS_DEPLOY_HOOKS') or '').strip()
    if not raw:
        raise SystemExit(
            'Automatic rollback is off: MORPHEUS_DEPLOY_HOOKS is not set (docs/UPDATING.md).'
        )
    try:
        config = json.loads(raw)
    except ValueError as exc:
        raise SystemExit(f'MORPHEUS_DEPLOY_HOOKS is not JSON: {exc}') from exc
    for key in ('webhook', 'repository', 'stores'):
        if not config.get(key):
            raise SystemExit(f'MORPHEUS_DEPLOY_HOOKS has no "{key}".')
    config.setdefault('branch', 'main')
    return config


def find_down(stores, expected, *, get, sleep, log) -> list[str]:
    """The stores that are down; the ones that are up or late are logged."""
    down = []
    for base in stores:
        state = classify(base, expected, get=get, sleep=sleep)
        if state == 'up':
            log(f'UP    {base} serves {expected}')
        elif state == 'late':
            log(
                f'LATE  {base} still serves an older version: queued, or its webhook was missed; left alone'
            )
        else:
            down.append(base)
    return down


def send_back(config, stores, down, previous, commit, *, post, log) -> list[str]:
    """Send each store that is down its push for ``previous``; the ones queued."""
    waiting = []
    for base in down:
        status, text = deploy_commit(
            config['webhook'],
            config['repository'],
            config['branch'],
            stores[base],
            commit,
            post=post,
        )
        if status == 200 and queued(text):
            log(f'BACK  {base}: putting back {previous} ({commit[:7]})')
            waiting.append(base)
        else:
            log(f'FAIL  {base}: the webhook queued nothing ({status}): {text[:200]}')
    return waiting


def wait_back(waiting, previous, *, get, sleep, log, clock) -> list[str]:
    """Wait, for all of them together, until each store serves ``previous``;
    the ones that never did. Coolify builds them one after another."""
    waiting, end = list(waiting), clock() + WAIT
    while waiting:
        for base in list(waiting):
            version, healthy = store_state(base, get)
            if healthy and version == previous:
                log(f'OK    {base} serves {previous} again')
                waiting.remove(base)
        if not waiting or clock() >= end:
            break
        sleep(CHECK_GAP)
    for base in waiting:
        log(f'FAIL  {base} did not come up on {previous} either')
    return waiting


def rollback(
    config,
    expected,
    tags,
    *,
    dry_run=False,
    get=http_get,
    post=http_post,
    sleep=time.sleep,
    commit_of=tag_commit,
    log=print,
    clock=time.monotonic,
) -> int:
    """Put back every store that is down on the previous release; the exit
    code: 0 when none was down, 1 otherwise (a rollback is a failed release)."""
    stores = {base.rstrip('/'): secret for base, secret in config['stores'].items()}
    down = find_down(stores, expected, get=get, sleep=sleep, log=log)
    if not down:
        return 0
    previous = previous_release(expected, tags)
    if previous is None:
        for base in down:
            log(f'FAIL  {base} is down, and there is no release older than {expected} to put back')
        return 1
    commit = commit_of(previous)
    if dry_run:
        for base in down:
            log(f'DOWN  {base}: would put back {previous} ({commit[:7]})')
        return 1
    waiting = send_back(config, stores, down, previous, commit, post=post, log=log)
    wait_back(waiting, previous, get=get, sleep=sleep, log=log, clock=clock)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Put back the stores a new release left down.')
    parser.add_argument('command', choices=['rollback'])
    parser.add_argument(
        '--dry-run', action='store_true', help='Say what would happen; send nothing.'
    )
    args = parser.parse_args(argv)
    config = load_config()
    expected = expected_version((ROOT / 'morph' / 'settings.py').read_text())
    return rollback(config, expected, release_tags(), dry_run=args.dry_run)


if __name__ == '__main__':
    sys.exit(main())
