"""
Lightweight in-process memory primitives for an agent run.

Three tiers:

* **Working** — scoped to a single `AgentRuntime.run()`. Cleared after.
* **Episodic** — bound to a specific user / session, persists across runs.
* **Semantic** — facts the agent has learned about a customer or merchant.

The `agent_core` plugin provides DB-backed implementations
(`AgentMemoryRecord`); this kernel module gives an in-memory fallback so
the runtime works in tests and without DB access.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import RLock
from typing import Any


@dataclass(slots=True)
class MemoryItem:
    key: str
    value: Any
    confidence: float = 1.0
    source: str = 'agent'


class WorkingMemory:
    """Per-run scratchpad."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def all(self) -> dict[str, Any]:
        return dict(self._store)


class _NamespacedStore:
    """In-memory keyed store; subclassed for episodic + semantic."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._data: dict[str, list[MemoryItem]] = defaultdict(list)

    def write(self, namespace: str, item: MemoryItem) -> None:
        with self._lock:
            existing = self._data[namespace]
            for i, e in enumerate(existing):
                if e.key == item.key:
                    existing[i] = item
                    return
            existing.append(item)

    def read(self, namespace: str, *, min_confidence: float = 0.0) -> list[MemoryItem]:
        with self._lock:
            return [m for m in self._data.get(namespace, []) if m.confidence >= min_confidence]

    def forget(self, namespace: str, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._data.pop(namespace, None)
            else:
                self._data[namespace] = [m for m in self._data.get(namespace, []) if m.key != key]


# Process-wide singletons for the in-memory tier.
episodic_memory = _NamespacedStore()
semantic_memory = _NamespacedStore()
