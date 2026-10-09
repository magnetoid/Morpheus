"""Which Janus this server runs, and whether GitHub has a newer one.

What is installed comes from :func:`core.assistant.janus_runtime.installed_build`
(pip's record of the image's git install, or the marker the auto-updater writes).

The newest commit on GitHub comes from the public API, at most once a day per
repository and ref (an hour after a failure), for the page. Installing it is the
auto-updater's job (core/assistant/janus_runtime.py), which keeps its own clock.
"""

from __future__ import annotations

import json
import logging
import re
from urllib.request import Request, urlopen

from django.core.cache import cache

from core.assistant.janus_runtime import installed_build

logger = logging.getLogger('morpheus.janus')

_DAY_S = 24 * 3600
_RETRY_S = 3600
_SHA = re.compile(r'^[0-9a-f]{40}$')


def latest_commit(repo: str, ref: str) -> dict | None:
    """``{sha, title, date}`` of ``ref`` on GitHub, or None when it can't be read."""
    key = f'janus:upstream:{repo}:{ref}'
    cached = cache.get(key)
    if cached is not None:
        return cached or None
    request = Request(  # noqa: S310 — a fixed https URL
        f'https://api.github.com/repos/{repo}/commits/{ref}',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'morpheus-janus-check'},
    )
    try:
        with urlopen(request, timeout=4) as resp:  # noqa: S310  # nosec B310 — fixed https host
            data = json.loads(resp.read().decode('utf-8'))
        commit = data.get('commit') or {}
        latest = {
            'sha': str(data.get('sha') or ''),
            'title': str(commit.get('message') or '').split('\n', 1)[0][:160],
            'date': str((commit.get('committer') or {}).get('date') or '')[:10],
        }
    except (OSError, ValueError, AttributeError):
        logger.info('janus: upstream check failed for %s@%s', repo, ref, exc_info=True)
        cache.set(key, {}, _RETRY_S)
        return None
    if not _SHA.match(latest['sha']):
        cache.set(key, {}, _RETRY_S)
        return None
    cache.set(key, latest, _DAY_S)
    return latest


def build_status(cmd: list[str] | None) -> dict:
    """The installed build, GitHub's latest, and ``state``: current, behind or unknown."""
    build = installed_build(cmd[0] if cmd else None)
    tracks_branch = bool(build['ref']) and not _SHA.match(build['ref'])
    status = {**build, 'tracks_branch': tracks_branch, 'latest': None, 'state': 'unknown'}
    if not (build['repo'] and build['commit']):
        return status
    latest = latest_commit(build['repo'], build['ref'] if tracks_branch else 'HEAD')
    if latest:
        status['latest'] = latest
        status['state'] = 'current' if latest['sha'] == build['commit'] else 'behind'
    return status
