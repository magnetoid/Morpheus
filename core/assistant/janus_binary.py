"""Finding the Janus program a turn runs, and naming its build.

Discovery order for the binary:
  1. ``settings.JANUS_BIN`` / ``JANUS_BIN``
  2. ``janus`` on PATH (the image's, pinned in the Dockerfile)
  3. ``<JANUS_ENGINE_ROOT>/.venv/bin/janus`` then ``venv/bin/janus``
  4. ``~/.janus/janus-agent`` source checkout (``python cli.py``)

A leaf of :mod:`core.assistant.janus_engine`, which re-exports every name here.
The functions in this file read each other here: a test that replaces one of them
for another patches this module, not the engine.
"""

from __future__ import annotations

import functools
import os
import shutil
import sys
from pathlib import Path


def _settings():
    try:
        from django.conf import settings

        return settings
    except Exception:  # noqa: BLE001
        return None


def engine_root() -> Path | None:
    s = _settings()
    raw = (getattr(s, 'JANUS_ENGINE_ROOT', '') if s else '') or os.environ.get(
        'JANUS_ENGINE_ROOT', ''
    )
    candidates = []
    if raw:
        candidates.append(Path(raw).expanduser())
    candidates.append(Path.home() / '.janus' / 'janus-agent')
    if s is not None:
        candidates.append(Path(s.BASE_DIR) / 'vendor' / 'janus')
    for p in candidates:
        if (p / 'cli.py').is_file() or (p / 'run_agent.py').is_file():
            return p
    return None


def janus_cmd() -> list[str] | None:
    s = _settings()
    explicit = (getattr(s, 'JANUS_BIN', '') if s else '') or os.environ.get('JANUS_BIN', '')
    if explicit:
        return [explicit]
    found = shutil.which('janus')
    if found:
        return [found]
    return _source_checkout_cmd()


@functools.lru_cache(maxsize=8)
def _build_of(path: str) -> tuple[str, str]:
    # A venv's Janus changes only with a new image, so the answer per path holds
    # for the life of the process.
    from core.assistant import janus_runtime

    try:
        build = janus_runtime.installed_build(path)
    except Exception:  # noqa: BLE001 — a reporting detail must never cost a turn
        return '', ''
    return build['version'], build['commit']


def build_of(cmd: list[str] | None) -> dict[str, str]:
    """Version and commit of the Janus ``cmd`` runs ('' where unknown)."""
    version, commit = _build_of(cmd[0]) if cmd else ('', '')
    return {'version': version, 'commit': commit}


def _source_checkout_cmd() -> list[str] | None:
    """A Janus source checkout (``JANUS_ENGINE_ROOT``, ``~/.janus/janus-agent``)."""
    root = engine_root()
    if root is None:
        return None
    for rel in ('.venv/bin/janus', 'venv/bin/janus'):
        bin_path = root / rel
        if bin_path.is_file():
            return [str(bin_path)]
    cli = root / 'cli.py'
    if cli.is_file():
        py = root / '.venv/bin/python'
        if not py.is_file():
            py = root / 'venv/bin/python'
        interpreter = str(py) if py.is_file() else sys.executable
        return [interpreter, str(cli)]
    return None
