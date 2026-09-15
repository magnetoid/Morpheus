"""What Janus learns, kept in the database instead of on a disk.

Janus, Linda's engine, keeps its learning as files in its home directory:

  * ``memories/MEMORY.md`` — its notes about the store, and ``memories/USER.md``
    — its notes about the person it talks to (entries joined by ``§``);
  * ``memories/daily/<date>.md`` — a journal of every memory change, which its
    ``recall_memory`` tool searches;
  * ``skills/<category>/<name>/`` — skills it wrote with ``skill_manage``;
  * ``learning/lessons.json`` — lessons it drew from past work.

A home is a temp dir: every redeploy wipes it, and each container has its own.
A disk volume would fix that only on hosts that offer one, and Morpheus must run
the same with or without Coolify. The database is the one store every
deployment already has, shared by every container and worker, so it holds the
durable copy (:class:`core.assistant.models.JanusLearning`) and each turn syncs:

  1. :func:`hydrate` writes the learned files into the conversation's home and
     removes any the database no longer has (the merchant deleted it, or it was
     learned before a redeploy on another container);
  2. Janus runs the turn, reading them and possibly writing new ones;
  3. :func:`harvest` diffs the home against what was hydrated and applies only
     the difference.

Harvest merges rather than overwrites, because two conversations can learn at
the same time: memory notes merge entry by entry, lessons by id, the journal by
the text appended, and any other file is replaced only when this turn changed it
and deleted only when nobody else changed it since.

``USER.md`` is kept per staff member. Everything else is shared by the store.

Deliberately not kept: ``state.db`` (the transcript — Morpheus stores the
conversation and replays recent history into the prompt), the skills Janus
bundles (re-copied on every run and listed in ``skills/.bundled_manifest``),
and anything that is not a small text document.

Learned content is model-written and may have been steered by something the
model read. It cannot grant anything: every store write still needs the
merchant's own approval at the MCP edge (``core/assistant/gates.py``). Janus
scans memory writes, re-scans memory at load, and scans agent-written skills
(``skills.guard_agent_created`` in the generated config). The merchant can review
and delete all of it on Settings → AI → Janus.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger('morpheus.assistant.janus_learning')

MEMORY_FILE = 'memories/MEMORY.md'
USER_FILE = 'memories/USER.md'
LESSONS_FILE = 'learning/lessons.json'
SKILLS_DIR = 'skills'
_JOURNAL_RE = re.compile(r'^memories/daily/\d{4}-\d{2}-\d{2}\.md$')
# One journal entry, as tools/memory_tool.py:append_daily_snapshot writes it:
# "- `HH:MM` **MEMORY** added: <note, continuation lines indented>".
_JOURNAL_ENTRY_RE = re.compile(r'^- `[^`]*` \*\*(MEMORY|USER)\*\* \w+: (.*)$', re.S)
_BUNDLED_MANIFEST = 'skills/.bundled_manifest'
_SKILL_NAME_RE = re.compile(r'^name:\s*["\']?([^"\'\n]+?)["\']?\s*$', re.M)

# Janus's own memory entry delimiter (tools/memory_tool.py). A memory file that
# does not re-serialise to exactly these bytes is treated by Janus as edited by
# something else, backed up, and locked against further writes.
ENTRY_DELIMITER = '\n§\n'

_SKILL_SUFFIXES = frozenset({'.md', '.txt', '.yaml', '.yml', '.json'})
# Janus's own SKILL.md limit.
MAX_FILE_CHARS = 100_000
MAX_FILES = 400
MAX_JOURNAL_DAYS = 90
MAX_LESSONS = 300
# A turn has at most 10 tool steps, so it cannot author this many files. More
# than this appearing at once means the home was misread (for example bundled
# skills without their manifest), and those files are not kept.
MAX_NEW_FILES_PER_TURN = 25


@dataclass
class Snapshot:
    """What :func:`hydrate` wrote, so :func:`harvest` can tell what the turn changed."""

    user_scope: str
    files: dict[str, str] = field(default_factory=dict)


def user_scope(user: Any) -> str:
    """The scope of one staff member's own notes, or '' when there is none."""
    if user is None or not getattr(user, 'is_staff', False) or not getattr(user, 'pk', None):
        return ''
    return f'user:{user.pk}'


def kind_of(path: str) -> str:
    if path in (MEMORY_FILE, USER_FILE):
        return 'memory'
    if _JOURNAL_RE.match(path):
        return 'journal'
    if path == LESSONS_FILE:
        return 'lesson'
    return 'skill'


def _is_learning_path(path: str) -> bool:
    if path in (MEMORY_FILE, USER_FILE, LESSONS_FILE) or _JOURNAL_RE.match(path):
        return True
    parts = path.split('/')
    return (
        len(parts) >= 3
        and parts[0] == SKILLS_DIR
        and not any(p in ('', '.', '..') or p.startswith('.') for p in parts)
        and Path(path).suffix.lower() in _SKILL_SUFFIXES
    )


def _read_text(path: Path) -> str | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return None
    return text if len(text) <= MAX_FILE_CHARS else None


def _bundled_skill_names(home: Path) -> set[str]:
    text = _read_text(home / _BUNDLED_MANIFEST) or ''
    return {line.partition(':')[0].strip() for line in text.splitlines() if line.strip()}


def _skill_name(skill_md: str, dir_name: str) -> str:
    if skill_md.startswith('---'):
        head = skill_md[3:].partition('\n---')[0]
        match = _SKILL_NAME_RE.search(head)
        if match:
            return match.group(1).strip()
    return dir_name


def _walk_files(top: Path):
    """Files under ``top``, never following a symlink or entering a dot directory."""
    for root, dirs, names in os.walk(top, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for name in names:
            yield Path(root) / name


def _learned_skill_dirs(home: Path) -> list[Path]:
    bundled = _bundled_skill_names(home)
    found = []
    for skill_md_path in _walk_files(home / SKILLS_DIR):
        if skill_md_path.name != 'SKILL.md':
            continue
        skill_md = _read_text(skill_md_path)
        skill_dir = skill_md_path.parent
        if skill_md is None or skill_dir.name in bundled:
            continue
        if _skill_name(skill_md, skill_dir.name) not in bundled:
            found.append(skill_dir)
    return found


def remove_bundled_skills(home: Path) -> None:
    """Delete the general-purpose skills Janus copied into a home, and its manifest.

    Janus seeds ~70 of its own skills (GitHub, notes apps, ML tooling) into every
    home and indexes them into the prompt with a rule to load one first. None is
    store work. The ``.no-bundled-skills`` marker stops new copies; this clears a
    home seeded before the marker existed. Learned skills are untouched.
    """
    import shutil

    manifest = home / _BUNDLED_MANIFEST
    bundled = _bundled_skill_names(home)
    if not bundled:
        return
    for skill_md_path in list(_walk_files(home / SKILLS_DIR)):
        if skill_md_path.name != 'SKILL.md' or not skill_md_path.exists():
            continue
        skill_dir = skill_md_path.parent
        text = _read_text(skill_md_path) or ''
        if skill_dir.name in bundled or _skill_name(text, skill_dir.name) in bundled:
            shutil.rmtree(skill_dir, ignore_errors=True)
    with contextlib.suppress(OSError):
        manifest.unlink()


def scan(home: Path) -> dict[str, str]:
    """The learned files in a Janus home: relative path → text."""
    candidates = [home / rel for rel in (MEMORY_FILE, USER_FILE, LESSONS_FILE)]
    daily = home / 'memories' / 'daily'
    if daily.is_dir():
        candidates += sorted(daily.iterdir())
    if (home / SKILLS_DIR).is_dir():
        for skill_dir in _learned_skill_dirs(home):
            candidates += list(_walk_files(skill_dir))
    files: dict[str, str] = {}
    for path in candidates:
        rel = path.relative_to(home).as_posix()
        if rel not in files and _is_learning_path(rel):
            text = _read_text(path)
            if text is not None:
                files[rel] = text
    return files


def _write(home: Path, rel: str, text: str) -> None:
    target = home / rel
    if not target.resolve().is_relative_to(home.resolve()):
        raise ValueError(f'learning path escapes the home: {rel}')
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix='.learn-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(text)
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _remove(home: Path, rel: str) -> None:
    target = home / rel
    with contextlib.suppress(OSError):
        target.unlink()
    # Drop directories the removal emptied, up to the skills root.
    stop = (home / SKILLS_DIR).resolve()
    parent = target.parent
    while parent.resolve() != stop and parent.resolve().is_relative_to(stop):
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def _rows(user_scope_: str):
    from core.assistant.models import JanusLearning

    scopes = [''] + ([user_scope_] if user_scope_ else [])
    return JanusLearning.objects.filter(scope__in=scopes)


def _wanted(row_scope: str, path: str, user_scope_: str) -> bool:
    if not _is_learning_path(path):
        return False
    if path == USER_FILE:
        return bool(user_scope_) and row_scope == user_scope_
    return row_scope == ''


def hydrate(home: Path, *, user: Any = None) -> Snapshot | None:
    """Make the home's learned files match the database. None if that failed."""
    scope = user_scope(user)
    try:
        wanted = {
            path: content
            for row_scope, path, content in _rows(scope).values_list('scope', 'path', 'content')
            if _wanted(row_scope, path, scope)
        }
        on_disk = scan(home)
        for rel in on_disk.keys() - wanted.keys():
            _remove(home, rel)
        for rel, content in wanted.items():
            if on_disk.get(rel) != content:
                _write(home, rel, content)
    except Exception:  # noqa: BLE001 — a failed sync must not cost the merchant the turn
        logger.warning('janus learning: hydrate failed', exc_info=True)
        return None
    return Snapshot(user_scope=scope, files=wanted)


def clear(home: Path) -> None:
    """Remove every learned file from a home (learning switched off)."""
    try:
        for rel in scan(home):
            _remove(home, rel)
    except Exception:  # noqa: BLE001
        logger.warning('janus learning: clear failed', exc_info=True)


def _entries(text: str | None) -> list[str]:
    return [e.strip() for e in (text or '').split(ENTRY_DELIMITER) if e.strip()]


def _merge_memory(base: str | None, turn: str | None, current: str | None) -> str | None:
    before, after, now = _entries(base), _entries(turn), _entries(current)
    removed = [e for e in before if e not in after]
    added = [e for e in after if e not in before]
    merged = [e for e in now if e not in removed] + [e for e in added if e not in now]
    return ENTRY_DELIMITER.join(merged) if merged else None


def _lesson_records(text: str | None) -> dict[str, dict] | None:
    if not text:
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    records: dict[str, dict] = {}
    for rec in data:
        if isinstance(rec, dict):
            key = str(rec.get('id') or json.dumps(rec, sort_keys=True))
            records[key] = rec
    return records


def _merge_lessons(base: str | None, turn: str | None, current: str | None) -> str | None:
    before, after, now = _lesson_records(base), _lesson_records(turn), _lesson_records(current)
    if after is None:
        return current  # Unreadable: keep what the database has.
    before, now = before or {}, now or {}
    removed = before.keys() - after.keys()
    merged = {k: v for k, v in now.items() if k not in removed}
    merged.update({k: v for k, v in after.items() if before.get(k) != v})
    records = list(merged.values())[-MAX_LESSONS:]
    return json.dumps(records, indent=2, ensure_ascii=False) + '\n' if records else None


def _journal_blocks(text: str) -> list[str]:
    """A journal split into its heading and one block per entry (with continuation lines)."""
    blocks: list[str] = []
    for line in text.splitlines(keepends=True):
        if not blocks or line.startswith('- `'):
            blocks.append(line)
        else:
            blocks[-1] += line
    return blocks


def _store_entries(text: str) -> str:
    """Only the journal entries about the store notes.

    Janus journals changes to USER.md too, and the journal is shared by the whole
    store, so an entry about one staff member would reach everyone's
    ``recall_memory``. Their notes are kept in their own USER.md only.
    """
    return ''.join(
        b
        for b in _journal_blocks(text)
        if (m := _JOURNAL_ENTRY_RE.match(b)) and m.group(1) == 'MEMORY'
    )


def _merge_journal(base: str | None, turn: str | None, current: str | None) -> str | None:
    if turn is None:
        return current  # Janus only appends; a vanished journal is not a deletion.
    base = base or ''
    appended = turn[len(base) :] if turn.startswith(base) else turn
    entries = _store_entries(appended)
    if not entries:
        return current
    if current is None:
        heading = _journal_blocks(turn)[0]
        return ('' if _JOURNAL_ENTRY_RE.match(heading) else heading) + entries
    return current + entries


def merge(path: str, base: str | None, turn: str | None, current: str | None) -> str | None:
    """The file's new content after a turn changed it from ``base`` to ``turn``,
    given the database now holds ``current``. None deletes it."""
    kind = kind_of(path)
    if kind == 'memory':
        return _merge_memory(base, turn, current)
    if kind == 'lesson':
        return _merge_lessons(base, turn, current)
    if kind == 'journal':
        return _merge_journal(base, turn, current)
    if turn is None:
        return None if current == base else current
    return turn


def harvest(
    home: Path, snapshot: Snapshot, *, conversation_key: str = '', user: Any = None
) -> list[str]:
    """Store what the turn learned. Returns the paths that changed. Never raises."""
    try:
        return _harvest(home, snapshot, conversation_key=conversation_key, user=user)
    except Exception:  # noqa: BLE001 — a failed sync must not fail the answered turn
        logger.warning('janus learning: harvest failed key=%s', conversation_key, exc_info=True)
        return []


def _harvest(home: Path, snapshot: Snapshot, *, conversation_key: str, user: Any) -> list[str]:
    from django.db import transaction

    from core.assistant.models import JanusLearning

    base = snapshot.files
    after = scan(home)
    changed = sorted(p for p in base.keys() | after.keys() if base.get(p) != after.get(p))
    if not snapshot.user_scope:
        changed = [p for p in changed if p != USER_FILE]
    new = [p for p in changed if p not in base]
    if len(new) > MAX_NEW_FILES_PER_TURN:
        logger.warning(
            'janus learning: %d new files in one turn; skill files not kept key=%s',
            len(new),
            conversation_key,
        )
        changed = [p for p in changed if p in base or kind_of(p) != 'skill']
    if not changed:
        return []

    def scope_of(path: str) -> str:
        return snapshot.user_scope if path == USER_FILE else ''

    applied: list[str] = []
    with transaction.atomic():
        rows = {
            (row.scope, row.path): row
            for row in JanusLearning.objects.select_for_update().filter(
                scope__in={scope_of(p) for p in changed}, path__in=changed
            )
        }
        count = JanusLearning.objects.count()
        for path in changed:
            row = rows.get((scope_of(path), path))
            current = row.content if row else None
            content = merge(path, base.get(path), after.get(path), current)
            if content == current:
                continue
            if content is None:
                row.delete()
                count -= 1
            elif row is not None:
                row.content = content
                row.conversation_key = conversation_key[:120]
                row.save(update_fields=['content', 'conversation_key', 'updated_at'])
            elif count >= MAX_FILES:
                logger.warning('janus learning: store full, %s not kept', path)
                continue
            else:
                JanusLearning.objects.create(
                    scope=scope_of(path),
                    path=path,
                    kind=kind_of(path),
                    content=content,
                    conversation_key=conversation_key[:120],
                )
                count += 1
            applied.append(path)
        _prune_journal()
    if applied:
        _audit('janus.learned', user, {'paths': applied[:50], 'conversation': conversation_key})
    return applied


def _prune_journal() -> None:
    from core.assistant.models import JanusLearning

    journal = JanusLearning.objects.filter(scope='', kind='journal').order_by('-path')
    stale = list(journal.values_list('pk', flat=True)[MAX_JOURNAL_DAYS:])
    if stale:
        JanusLearning.objects.filter(pk__in=stale).delete()


def _audit(event_type: str, user: Any, metadata: dict) -> None:
    try:
        from core.audit.services import record

        record(event_type=event_type, actor=user, target='janus', metadata=metadata)
    except Exception:  # noqa: BLE001 — audit must never break the sync
        logger.debug('janus learning: audit skipped', exc_info=True)


# ── Review (Settings → AI → Janus) ──────────────────────────────────────────


def note_id(entry: str) -> str:
    return hashlib.sha256(entry.encode('utf-8')).hexdigest()[:16]


def notes(*, user: Any = None) -> dict[str, list[dict]]:
    """Janus's notes about the store, and its notes about this staff member."""
    from core.assistant.models import JanusLearning

    out: dict[str, list[dict]] = {'store': [], 'user': []}
    for key, scope, path in (('store', '', MEMORY_FILE), ('user', user_scope(user), USER_FILE)):
        if key == 'user' and not scope:
            continue
        row = JanusLearning.objects.filter(scope=scope, path=path).first()
        if row is not None:
            out[key] = [{'id': note_id(e), 'text': e} for e in _entries(row.content)]
    return out


def forget_note(*, which: str, entry_id: str, user: Any = None) -> bool:
    """Delete one note. ``which`` is 'store' or 'user' (the viewer's own notes)."""
    from django.db import transaction

    from core.assistant.models import JanusLearning

    scope, path = ('', MEMORY_FILE) if which == 'store' else (user_scope(user), USER_FILE)
    if which not in ('store', 'user') or (which == 'user' and not scope):
        return False
    with transaction.atomic():
        row = JanusLearning.objects.select_for_update().filter(scope=scope, path=path).first()
        if row is None:
            return False
        entries = _entries(row.content)
        kept = [e for e in entries if note_id(e) != entry_id]
        if len(kept) == len(entries):
            return False
        if kept:
            row.content = ENTRY_DELIMITER.join(kept)
            row.save(update_fields=['content', 'updated_at'])
        else:
            row.delete()
        if which == 'store':
            forgotten = next(e for e in entries if note_id(e) == entry_id)
            _scrub_journal(forgotten)
    _audit('janus.learning_forgotten', user, {'what': f'{which} note'})
    return True


def _scrub_journal(entry: str) -> None:
    """Remove a deleted note from the journal, or ``recall_memory`` would still find it."""
    from core.assistant.models import JanusLearning

    body = entry.strip().replace('\n', '\n  ')  # how Janus journals a multi-line note
    for row in JanusLearning.objects.select_for_update().filter(scope='', kind='journal'):
        blocks = _journal_blocks(row.content)
        kept = [
            b
            for b in blocks
            if not ((m := _JOURNAL_ENTRY_RE.match(b)) and m.group(2).rstrip('\n') == body)
        ]
        if len(kept) == len(blocks):
            continue
        if any(_JOURNAL_ENTRY_RE.match(b) for b in kept):
            row.content = ''.join(kept)
            row.save(update_fields=['content', 'updated_at'])
        else:
            row.delete()


def skills() -> list[dict]:
    """Skills Janus wrote, one entry per skill directory."""
    from core.assistant.models import JanusLearning

    rows = list(JanusLearning.objects.filter(scope='', kind='skill').order_by('path'))
    dirs = sorted({r.path.rsplit('/', 1)[0] for r in rows if r.path.endswith('/SKILL.md')})
    out = []
    for skill_dir in dirs:
        members = [r for r in rows if r.path.startswith(skill_dir + '/')]
        main = next(r for r in members if r.path == f'{skill_dir}/SKILL.md')
        head = main.content[3:].partition('\n---')[0] if main.content.startswith('---') else ''
        desc = re.search(r'^description:\s*["\']?(.+?)["\']?\s*$', head, re.M)
        out.append(
            {
                'dir': skill_dir,
                'name': _skill_name(main.content, skill_dir.rsplit('/', 1)[-1]),
                'description': desc.group(1)[:300] if desc else '',
                'files': len(members),
                'updated_at': max(r.updated_at for r in members),
            }
        )
    return out


def delete_skill(skill_dir: str, *, user: Any = None) -> int:
    from core.assistant.models import JanusLearning

    if skill_dir not in {s['dir'] for s in skills()}:
        return 0
    deleted, _ = JanusLearning.objects.filter(
        scope='', kind='skill', path__startswith=skill_dir + '/'
    ).delete()
    if deleted:
        _audit('janus.learning_forgotten', user, {'what': 'skill', 'skill': skill_dir})
    return deleted


def lesson_count() -> int:
    from core.assistant.models import JanusLearning

    row = JanusLearning.objects.filter(scope='', path=LESSONS_FILE).first()
    return len(_lesson_records(row.content) or {}) if row else 0


def clear_lessons(*, user: Any = None) -> bool:
    from core.assistant.models import JanusLearning

    deleted, _ = JanusLearning.objects.filter(scope='', path=LESSONS_FILE).delete()
    if deleted:
        _audit('janus.learning_forgotten', user, {'what': 'lessons'})
    return bool(deleted)
