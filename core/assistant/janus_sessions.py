"""What a conversation's Janus sessions leave in its home: the session id a
follow-up resumes, and what ``state.db`` says the home spent and replied.

A leaf of :mod:`core.assistant.janus_engine`, which re-exports every name here.
The functions in this file read each other here: a test that replaces one of them
for another patches this module, not the engine.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger('morpheus.assistant.janus')

# Janus prints ``session_id: <id>`` to stderr in quiet mode. Stored per
# conversation and passed back with ``--resume``: a bare ``--continue`` looks up
# the newest session whose source is ``cli``, never ``linda``, so it failed every
# follow-up message. Validated before it reaches argv.
_SESSION_FILE = 'janus_session.json'
_SESSION_ID_RE = re.compile(r'^[A-Za-z0-9_.:-]{1,128}$')
_SESSION_LINE_RE = re.compile(r'^session_id:\s*(\S+)\s*$', re.M)

# A resumed session sends its whole transcript on every model call, and Janus only
# compresses at half the model's context (500K tokens for a 1M model), so a
# conversation that never starts over costs more on every message. Start a fresh
# session, with a short recap of recent history, after this many turns or this
# long idle. A fresh session also picks up notes learned in other conversations.
SESSION_MAX_TURNS = 20
SESSION_IDLE_S = 6 * 3600


def _session_meta(conv_home: Path) -> dict[str, Any]:
    try:
        meta = json.loads((conv_home / _SESSION_FILE).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


def _stored_session_id(conv_home: Path) -> str:
    """The session to resume, or '' to start a fresh one."""
    meta = _session_meta(conv_home)
    sid = str(meta.get('id') or '')
    if not _SESSION_ID_RE.match(sid):
        return ''
    try:
        turns, last_at = int(meta.get('turns') or 0), float(meta.get('last_at') or 0)
    except (TypeError, ValueError):
        return ''
    if turns >= SESSION_MAX_TURNS or time.time() - last_at > SESSION_IDLE_S:
        return ''
    return sid


def _save_session_meta(conv_home: Path, **changes: Any) -> None:
    with contextlib.suppress(OSError):
        (conv_home / _SESSION_FILE).write_text(
            json.dumps({**_session_meta(conv_home), **changes}), encoding='utf-8'
        )


def _remember_session_id(conv_home: Path, stderr: str) -> str:
    match = _SESSION_LINE_RE.search(stderr)
    if not (match and _SESSION_ID_RE.match(match.group(1))):
        return ''
    sid = match.group(1)
    meta = _session_meta(conv_home)
    turns = int(meta.get('turns') or 0) + 1 if meta.get('id') == sid else 1
    _save_session_meta(conv_home, id=sid, turns=turns, last_at=time.time())
    return sid


def _forget_session_id(conv_home: Path) -> None:
    # The file stays: it also holds what the home has been billed for.
    _save_session_meta(conv_home, id='', turns=0)


_USAGE_COLUMNS = (
    'input_tokens',
    'output_tokens',
    'cache_read_tokens',
    'cache_write_tokens',
    'reasoning_tokens',
    'api_call_count',
    'estimated_cost_usd',
)


def _home_usage(conv_home: Path, session_id: str = '') -> dict[str, Any]:
    """Janus's token and cost totals over every session in the home's state.db.

    A home is one conversation, so the sum is all that conversation ever spent,
    whichever session spent it: a turn that died before it was counted, or the
    session a context compression ended while this turn went on in a new one.
    ``model`` is the named session's, else the newest session's.
    """
    db = conv_home / 'state.db'
    if not db.is_file():
        return {}
    sums = ', '.join(f'SUM({column})' for column in _USAGE_COLUMNS)
    try:
        with contextlib.closing(sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=2)) as conn:
            totals = conn.execute(f'SELECT {sums} FROM sessions').fetchone()  # noqa: S608 — fixed column list  # nosec B608
            model = conn.execute(
                'SELECT model FROM sessions ORDER BY id = ? DESC, rowid DESC LIMIT 1',
                (session_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.debug('janus: usage unreadable', exc_info=True)
        return {}
    return {
        'model': (model[0] if model else '') or '',
        **{k: totals[i] or 0 for i, k in enumerate(_USAGE_COLUMNS)},
    }


def _counted_usage(conv_home: Path) -> dict[str, Any]:
    """The home's totals that earlier turns were already billed for.

    Kept beside the session id. A turn's spend is the home's total after it less
    this figure, so a turn nobody counted (its process died) is billed by the
    next one. A home without the figure starts from its total as it is now: its
    history was billed turn by turn. Never above a total that could be read,
    which drops when Janus prunes old sessions.
    """
    total = _home_usage(conv_home)
    counted = _session_meta(conv_home).get('counted')
    if not isinstance(counted, dict):
        # Stored now, so the first turn is covered too if it dies uncounted.
        counted = {k: total.get(k) or 0 for k in _USAGE_COLUMNS}
        _save_session_meta(conv_home, counted=counted)
    elif total:
        counted = {k: min(counted.get(k) or 0, total[k]) for k in _USAGE_COLUMNS}
    return counted


def _bill(conv_home: Path, counted: dict[str, Any], session_id: str) -> dict[str, Any]:
    """What the home spent since ``counted``, which now counts it too."""
    total = _home_usage(conv_home, session_id)
    usage = _turn_usage(counted, total)
    if usage:
        _save_session_meta(conv_home, counted={k: total[k] for k in _USAGE_COLUMNS})
    return usage


# `janus chat -q` records its sessions with source 'cli' whatever --source says;
# 'linda' stays for a build that honours it. Each home's state.db holds one
# conversation, so the source never has to tell sessions apart.


def _session_started_since(conv_home: Path, since: float) -> str:
    """The Linda session Janus started at or after `since`, or ''."""
    db = conv_home / 'state.db'
    if not db.is_file():
        return ''
    try:
        with contextlib.closing(sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=2)) as conn:
            row = conn.execute(
                "SELECT id FROM sessions WHERE source IN ('cli', 'linda') AND started_at >= ? "
                'ORDER BY started_at DESC LIMIT 1',
                (since,),
            ).fetchone()
    except sqlite3.Error:
        logger.debug('janus: session lookup failed', exc_info=True)
        return ''
    return str(row[0]) if row and _SESSION_ID_RE.match(str(row[0] or '')) else ''


def _recover_reply(conv_home: Path, resume_id: str, since: float) -> tuple[str, str]:
    """The session and last assistant reply this turn wrote to state.db, if any."""
    db = conv_home / 'state.db'
    if not db.is_file():
        return '', ''
    try:
        with contextlib.closing(sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=2)) as conn:
            row = conn.execute(
                'SELECT m.session_id, m.content FROM messages m JOIN sessions s ON s.id = m.session_id '
                "WHERE s.source IN ('cli', 'linda') AND m.role = 'assistant' "
                'AND m.timestamp >= ? '
                "AND COALESCE(m.content, '') != '' AND (s.id = ? OR s.started_at >= ?) "
                'ORDER BY m.id DESC LIMIT 1',
                (since, resume_id, since),
            ).fetchone()
    except sqlite3.Error:
        logger.debug('janus: reply recovery failed', exc_info=True)
        return '', ''
    if not row or not _SESSION_ID_RE.match(str(row[0] or '')):
        return '', ''
    return str(row[0]), _strip_notices(str(row[1]))


def _turn_usage(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """What a turn added to the totals (they accumulate); never negative."""
    if not after:
        return {}
    usage = {k: max(0, (after.get(k) or 0) - (before.get(k) or 0)) for k in _USAGE_COLUMNS}
    usage['model'] = after.get('model') or ''
    return usage


# Status lines Janus prints to stdout even under -Q, which would otherwise be
# glued onto the answer.
_NOTICE_PREFIXES = ('⚠️  Reached maximum iterations', '❌ All API retries exhausted')


def _strip_notices(stdout: str) -> str:
    lines = [ln for ln in stdout.splitlines() if not ln.lstrip().startswith(_NOTICE_PREFIXES)]
    return '\n'.join(lines).strip()
