"""Which Janus Linda runs: the build an install records, and its contract report.

The image installs Janus from git at build time (Dockerfile: ``JANUS_REF``, a
reviewed commit) and checks it against Morpheus's contract
(:mod:`core.assistant.janus_contract`). Janus changes only when a Morpheus release
moves that pin, by the pull request ``.github/workflows/janus-bump.yml`` opens
after testing the new commit. Nothing here installs or switches a Janus: the
store-side self-updater was retired in v0.175.1, once the pin moved by pull
request (docs/plans/janus-alignment-and-app-platform-2026-11.md, P3b).
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

# Installed alongside Janus, exactly as the Dockerfile pins them. Read by
# scripts/bump_janus.py, which every workflow that installs Janus goes through.
PINS = ('ddgs==9.16.0', 'primp==2.0.1')
# The Docker build writes the contract report here, inside the Janus venv.
CONTRACT_FILE = 'morpheus-contract.json'

_GITHUB = re.compile(r'^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$')
_ARCHIVE = re.compile(r'^https://github\.com/([\w.-]+)/([\w.-]+)/archive/([0-9a-f]{40})\.tar\.gz$')


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def venv_of(janus_bin: str | None) -> Path | None:
    """The venv a ``janus`` executable belongs to (follows the /usr/local/bin link)."""
    if not janus_bin:
        return None
    exe = shutil.which(janus_bin) or janus_bin
    return Path(os.path.realpath(exe)).parent.parent


def installed_build(janus_bin: str | None) -> dict:
    """Version, commit, ref and repository of a Janus install; '' where unknown.

    Read from pip's ``direct_url.json``: a git install (the image, CI) names the
    commit and the ref it asked for, an install from GitHub's archive of a commit
    (a local conformance run) names the commit in its URL.
    """
    build = {'version': '', 'commit': '', 'ref': '', 'repo': '', 'url': ''}
    venv = venv_of(janus_bin)
    if venv is None:
        return build
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
        build['ref'] = str(vcs.get('requested_revision') or '')
        break
    return build


def contract_report(janus_bin: str | None) -> dict:
    """The contract report the Docker build recorded for this Janus, or {}."""
    venv = venv_of(janus_bin)
    return _read_json(venv / CONTRACT_FILE) if venv else {}
