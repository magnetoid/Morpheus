"""What one agent run spent, by the model that answered.

The runtime adds every provider answer here, the summary calls of context
compaction included. The caller that owns the run's row creates the meter, so
it can still read it when the run never returns: a run that timed out, or one
that raised after its first answers.

A run is priced by its row's ``model``. When another model answered part of it
(the fallback router's secondary), the row also keeps the split under
``USAGE_KEY`` in its metadata, and the spend cap prices each share by its own
model (``guardrails.daily_spend_usd``).
"""

from __future__ import annotations

import threading

#: The metadata key on an ``AgentRun`` whose answers came from more than its own
#: model: ``{model: [prompt_tokens, completion_tokens]}``.
USAGE_KEY = 'usage_by_model'


class RunUsage:
    """Tokens per answering model. Safe to read from another thread while the
    run still adds to it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_model: dict[str, list[int]] = {}

    def add(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        pt, ct = int(prompt_tokens or 0), int(completion_tokens or 0)
        if not (pt or ct):
            return
        with self._lock:
            pair = self._by_model.setdefault(model or '', [0, 0])
            pair[0] += pt
            pair[1] += ct

    def by_model(self) -> dict[str, tuple[int, int]]:
        with self._lock:
            return {model: (pair[0], pair[1]) for model, pair in self._by_model.items()}

    @property
    def prompt_tokens(self) -> int:
        return sum(pt for pt, _ct in self.by_model().values())

    @property
    def completion_tokens(self) -> int:
        return sum(ct for _pt, ct in self.by_model().values())
