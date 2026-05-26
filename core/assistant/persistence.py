"""
Crash-resilient persistence for the Assistant.

The store has two backends and decides per-write which to use:

1. **DB-backed** — `AssistantConversation` + `AssistantMessage` rows
   (defined as a Django app under `core/assistant/models.py`). Used when
   the database is reachable.

2. **JSONL fallback** — `~/.morpheus/assistant/<session>.jsonl`. Used
   when the DB is down. The chat surface stays usable; rows can be
   replayed into the DB later via a management command (out of scope for
   this PR).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger('morpheus.assistant.store')


def _fallback_dir() -> Path:
    base = os.environ.get('MORPHEUS_ASSISTANT_FALLBACK', '/tmp/morpheus-assistant')
    p = Path(base)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Last-resort: a temp dir that's always writable.
        p = Path('/tmp/morpheus-assistant-fallback')
        p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class StoredMessage:
    role: str
    # `content` defaults to '' because tool-role messages carry their
    # payload in `tool_output` (structured) rather than as plain text;
    # forcing content there would just be `''` boilerplate at every
    # call site and was the source of a TypeError in the Linda runtime.
    content: str = ''
    tool_name: str = ''
    tool_args: dict = field(default_factory=dict)
    tool_output: Any = None
    at: str = ''


class AssistantStore:
    """Read/write conversation history. Always succeeds — falls back to disk."""

    def __init__(self, *, prefer_db: bool = True) -> None:
        self.prefer_db = prefer_db

    def append(self, *, conversation_key: str, message: StoredMessage) -> str:
        """Append a message. `conversation_key` is e.g. user pk or 'session:abc'."""
        message.at = message.at or datetime.now(timezone.utc).isoformat()
        if self.prefer_db and self._db_append(conversation_key, message):
            return 'db'
        self._file_append(conversation_key, message)
        return 'file'

    def history(self, *, conversation_key: str, limit: int = 30) -> list[StoredMessage]:
        if self.prefer_db:
            db_rows = self._db_history(conversation_key, limit)
            if db_rows is not None:
                return db_rows
        return self._file_history(conversation_key, limit)

    # ── DB backend ────────────────────────────────────────────────────────────

    def _db_append(self, key: str, m: StoredMessage) -> bool:
        try:
            from django.db import DatabaseError
            from core.assistant.models import AssistantConversation, AssistantMessage
        except Exception:  # noqa: BLE001
            return False
        try:
            conv, _ = AssistantConversation.objects.get_or_create(key=key)
            AssistantMessage.objects.create(
                conversation=conv,
                role=m.role, content=m.content[:50_000],
                tool_name=m.tool_name[:200],
                tool_args=m.tool_args or {},
                tool_output=(m.tool_output if isinstance(m.tool_output, (dict, list))
                             else {'value': str(m.tool_output)[:5_000]}) if m.tool_output is not None else {},
            )
            return True
        except DatabaseError as e:
            logger.warning('assistant: DB append failed, falling back to file: %s', e)
            return False
        except Exception as e:  # noqa: BLE001
            logger.warning('assistant: DB append unexpected: %s', e)
            return False

    def _db_history(self, key: str, limit: int) -> list[StoredMessage] | None:
        try:
            from django.db import DatabaseError
            from core.assistant.models import AssistantConversation, AssistantMessage
        except Exception:  # noqa: BLE001
            return None
        try:
            conv = AssistantConversation.objects.filter(key=key).first()
            if conv is None:
                return []
            rows = list(
                AssistantMessage.objects
                .filter(conversation=conv)
                .order_by('-created_at')[:limit]
            )
            rows.reverse()
            return [
                StoredMessage(
                    role=r.role, content=r.content,
                    tool_name=r.tool_name,
                    tool_args=r.tool_args or {},
                    tool_output=r.tool_output,
                    at=r.created_at.isoformat(),
                )
                for r in rows
            ]
        except DatabaseError as e:
            logger.warning('assistant: DB history failed: %s', e)
            return None

    # ── File backend ──────────────────────────────────────────────────────────

    def _file_path(self, key: str) -> Path:
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in key)[:80]
        return _fallback_dir() / f'{safe}.jsonl'

    def _file_append(self, key: str, m: StoredMessage) -> None:
        try:
            with self._file_path(key).open('a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(m), default=str) + '\n')
        except OSError as e:
            logger.error('assistant: file fallback append failed: %s', e)

    def _file_history(self, key: str, limit: int) -> list[StoredMessage]:
        path = self._file_path(key)
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding='utf-8').splitlines()[-limit:]
        except OSError:
            return []
        out: list[StoredMessage] = []
        for line in lines:
            try:
                d = json.loads(line)
                out.append(StoredMessage(**d))
            except (ValueError, TypeError):
                continue
        return out


_DEFAULT_STORE = None


def get_default_store() -> AssistantStore:
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = AssistantStore()
    return _DEFAULT_STORE
