#!/usr/bin/env python3
"""Put a store back on the release it ran before, when a new one leaves it down.

Run by .github/workflows/deploy-smoke.yml after scripts/deploy_smoke.sh fails
(safe deploys, part 3); after a green smoke, a dry run shows it can still see
every store. Standard library only: CI runs it with the system Python.

A store is put back only when it is down: never when it is late, and never
when the guard cannot tell. One that still serves an older version is queued
behind the others, or missed its webhook, and is left alone. A container swap
answers 503 for a minute or more, so a store counts as down only after
DOWN_AFTER seconds without a healthy answer; every store is checked each round,
so they share that wait. A 401, 403 or 429 comes from something in front of the
store refusing the guard (a Cloudflare rule), not from the store: a store that
only ever answers that is reported and left alone.

A store goes back to the release it served when the smoke started
(SMOKE_BEFORE_FILE, written by scripts/deploy_smoke.sh), else to the newest
release older than this one, so a store this guard already put back once goes
back to the release that worked there. Going back more than one release is
refused when a migration added since carries ``morpheus_contract``: the
migration gate checks that such a migration is safe for the release just before
its own, not for older ones.

It puts a store back by sending that store's Coolify manual GitHub webhook a
signed push event naming that release tag's commit: Coolify deploys the
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
import http.client
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
DOWN_AFTER = 8 * 60  # a store with no healthy answer for this long is down
CHECK_GAP = 20  # seconds between rounds of checks
WAIT = 30 * 60  # how long the stores put back get to come up, together
REFUSED = frozenset({401, 403, 429})  # something in front of the store refused the guard
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


def next_release(release: str, tags: list[str]) -> str | None:
    """The oldest release tag newer than ``release``."""
    floor = version_key(release)
    if floor is None:
        return None
    newer = [tag for tag in tags if (key := version_key(tag)) is not None and key > floor]
    return min(newer, key=version_key) if newer else None


def _body(response) -> str:
    try:
        return response.read().decode('utf-8', 'replace')
    except (http.client.HTTPException, OSError):
        return ''


def http_get(url: str, timeout: float = 15) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={'User-Agent': 'morpheus-deploy-guard'})  # noqa: S310 — configured https URLs
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310  # nosec B310 — configured https URLs
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return exc.code, _body(exc)
    except (urllib.error.URLError, http.client.HTTPException, OSError):
        # A malformed answer (BadStatusLine, IncompleteRead) is no answer.
        return 0, ''


def http_post(url: str, body: bytes, headers: dict, timeout: float = 30) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')  # noqa: S310 — the configured webhook
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310  # nosec B310 — the configured webhook
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return exc.code, _body(exc)
    except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
        return 0, str(exc)


def store_state(base: str, get=http_get) -> tuple[str, str]:
    """``(version, state)``: the version /readyz reports, and 'ok' (/readyz
    ``ok`` and the home page 200), 'refused' (a 401, 403 or 429 from something
    in front of the store) or 'bad'."""
    status, body = get(f'{base}/readyz')
    if status in REFUSED:
        return '', 'refused'
    try:
        data = json.loads(body) if status == 200 else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    version = str(data.get('version') or '')
    if data.get('status') != 'ok':
        return version, 'bad'
    home, _ = get(f'{base}/')
    if home in REFUSED:
        return version, 'refused'
    return version, 'ok' if home == 200 else 'bad'


def classify_all(stores, expected, *, get=http_get, sleep=time.sleep, clock=time.monotonic) -> dict:
    """Each store's state: 'up' (healthy on ``expected``), 'late' (healthy on
    another version), 'down' (no healthy answer for DOWN_AFTER seconds) or
    'unknown' (no healthy answer either, but refused at least once, so it may
    be fine). Every store is checked each round, so they share the wait."""
    states, refused, end = {}, set(), clock() + DOWN_AFTER
    while True:
        for base in stores:
            if base in states:
                continue
            version, state = store_state(base, get)
            if state == 'ok':
                states[base] = 'up' if version == expected else 'late'
            elif state == 'refused':
                refused.add(base)
        if len(states) == len(stores) or clock() >= end:
            break
        sleep(CHECK_GAP)
    return {base: states.get(base) or ('unknown' if base in refused else 'down') for base in stores}


def read_before(path: str) -> dict:
    """What each store served when the smoke started: the ``base version`` lines
    scripts/deploy_smoke.sh writes; {} without that file."""
    try:
        text = Path(path).read_text() if path else ''
    except OSError:
        return {}
    pairs = (line.split() for line in text.splitlines())
    return {parts[0].rstrip('/'): parts[1] for parts in pairs if len(parts) == 2}


def target_release(base: str, expected: str, tags: list[str], before: dict) -> str | None:
    """The release ``base`` goes back to: the one it served when the smoke
    started, when that is a release older than ``expected``; else the newest
    release older than ``expected``."""
    served, ceiling = before.get(base, ''), version_key(expected)
    key = version_key(served)
    if served in tags and key is not None and ceiling is not None and key < ceiling:
        return served
    return previous_release(expected, tags)


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


def contract_migrations(release: str, tags: list[str]) -> str:
    """The migrations added after the release that followed ``release`` that
    carry ``morpheus_contract``, comma-separated; '' when there is none."""
    following = next_release(release, tags)
    if following is None:
        return ''
    added = _git(
        'diff', '--name-only', '--diff-filter=A', f'{following}..HEAD', '--', '*/migrations/0*.py'
    ).split()
    contracts = []
    for path in added:
        try:
            if 'morpheus_contract' in (ROOT / path).read_text():
                contracts.append(path)
        except OSError:
            contracts.append(path)  # unreadable: assume the worst
    return ', '.join(contracts)


def report(states: dict, expected: str, log) -> None:
    for base, state in states.items():
        if state == 'up':
            log(f'UP    {base} serves {expected}')
        elif state == 'late':
            log(
                f'LATE  {base} still serves an older version: queued, or its webhook was missed; left alone'
            )
        elif state == 'unknown':
            log(
                f'?     {base}: cannot tell, something in front of it refused the guard '
                '(401, 403 or 429); left alone'
            )


def choose_targets(down, expected, tags, before, *, contract_of, log) -> dict:
    """The release each store that is down goes back to; a store it cannot
    choose one for is logged and left."""
    previous, targets = previous_release(expected, tags), {}
    for base in down:
        release = target_release(base, expected, tags, before)
        if release is None:
            log(f'FAIL  {base} is down, and there is no release older than {expected} to put back')
            continue
        contracts = contract_of(release) if release != previous else ''
        if contracts:
            log(
                f'FAIL  {base} is down. It ran {release} before this deploy, but {contracts} '
                f'carries morpheus_contract, which is checked only against the release before '
                f'its own, so {release} may not run on that database. Not put back: put it back '
                'by hand (docs/OPERATIONS_RUNBOOK.md, Rollback).'
            )
            continue
        targets[base] = release
    return targets


def send_back(config, stores, targets, *, commit_of, post, log) -> dict:
    """Send each store the push for its release; the stores queued, with that release."""
    waiting = {}
    for base, release in targets.items():
        commit = commit_of(release)
        status, text = deploy_commit(
            config['webhook'],
            config['repository'],
            config['branch'],
            stores[base],
            commit,
            post=post,
        )
        if status == 200 and queued(text):
            log(f'BACK  {base}: putting back {release} ({commit[:7]})')
            waiting[base] = release
        else:
            log(f'FAIL  {base}: the webhook queued nothing ({status}): {text[:200]}')
    return waiting


def wait_back(waiting, expected, *, get, sleep, log, clock) -> list[str]:
    """Wait, for all of them together, until each store serves the release it
    was sent; the ones that never did. Coolify builds them one after another."""
    waiting, end, noted = dict(waiting), clock() + WAIT, set()
    while waiting:
        for base, release in list(waiting.items()):
            version, state = store_state(base, get)
            if state != 'ok':
                continue
            if version == release:
                log(f'OK    {base} serves {release} again')
                del waiting[base]
            elif version == expected and base not in noted:
                noted.add(base)
                log(
                    f'NOTE  {base} came up on {expected} after all; {release} is queued '
                    'and will replace it'
                )
        if not waiting or clock() >= end:
            break
        sleep(CHECK_GAP)
    for base, release in waiting.items():
        log(f'FAIL  {base} did not come up on {release} either')
    return list(waiting)


def rollback(
    config,
    expected,
    tags,
    *,
    dry_run=False,
    before=None,
    get=http_get,
    post=http_post,
    sleep=time.sleep,
    clock=time.monotonic,
    commit_of=tag_commit,
    contract_of=None,
    log=print,
) -> int:
    """Put back every store that is down; the exit code: 0 when every store is
    up or late, 1 otherwise (a rollback is still a failed release, and a store
    the guard cannot see needs a person)."""
    stores = {base.rstrip('/'): secret for base, secret in config['stores'].items()}
    states = classify_all(list(stores), expected, get=get, sleep=sleep, clock=clock)
    report(states, expected, log)
    down = [base for base, state in states.items() if state == 'down']
    if not down:
        return 0 if set(states.values()) <= {'up', 'late'} else 1
    if contract_of is None:
        contract_of = lambda release: contract_migrations(release, tags)  # noqa: E731
    targets = choose_targets(down, expected, tags, before or {}, contract_of=contract_of, log=log)
    if dry_run:
        for base, release in targets.items():
            log(f'DOWN  {base}: would put back {release} ({commit_of(release)[:7]})')
        return 1
    waiting = send_back(config, stores, targets, commit_of=commit_of, post=post, log=log)
    wait_back(waiting, expected, get=get, sleep=sleep, log=log, clock=clock)
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
    before = read_before(os.environ.get('SMOKE_BEFORE_FILE', ''))
    return rollback(config, expected, release_tags(), dry_run=args.dry_run, before=before)


if __name__ == '__main__':
    sys.exit(main())
