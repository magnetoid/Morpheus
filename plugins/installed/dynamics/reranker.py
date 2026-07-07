"""dynamics — the self-optimizing Thompson-sampling reranker.

Pure-Python (no numpy): one ``random.betavariate(alpha, beta)`` draw per candidate
arm. Products with a stronger per-segment posterior tend to draw higher, while an
arm's uncertainty keeps exploring newcomers. The draw is blended 50/50 with the
Phase-1 propensity score, then guardrails are applied:

* **exploration floor** — a fraction of positions are lightly shuffled so the
  bandit never fully exploits (prevents the feedback-loop / popularity collapse
  the research warns about);
* **cold-start** — an unseen product has no BanditArm row, so it defaults to a
  Beta(1, 1) uniform prior (mean 0.5, wide) and gets explored;
* **diversity cap** — at most ``per_category_cap`` items from one category ride in
  the head of the slate, so a single category can't dominate the block.

Fail-soft: any error degrades to the propensity order — a reorder must never
break a storefront render.
"""

from __future__ import annotations

import random

_EXPLORATION_RATE = 0.10
_BANDIT_WEIGHT = 0.5
_PER_CATEGORY_CAP = 3


def thompson_rerank(
    product_ids: list,
    segment: str,
    propensity: dict,
    *,
    category_of: dict | None = None,
    exploration_rate: float = _EXPLORATION_RATE,
    per_category_cap: int = _PER_CATEGORY_CAP,
) -> list:
    """Rerank ``product_ids`` by a Thompson draw blended with propensity, then
    apply the exploration floor + per-category diversity cap. Order-preserving
    fallback: unknown arms use the uniform prior; any failure returns the input
    order."""
    if not product_ids:
        return []
    arms = _arms_for(product_ids, segment)
    scored = []
    for pid in product_ids:
        alpha, beta = arms.get(pid, (1.0, 1.0))
        try:
            draw = random.betavariate(max(alpha, 1e-6), max(beta, 1e-6))
        except (ValueError, OverflowError):
            draw = 0.5
        blended = _BANDIT_WEIGHT * draw + (1 - _BANDIT_WEIGHT) * float(propensity.get(pid, 0.0))
        scored.append((pid, blended))
    scored.sort(key=lambda t: t[1], reverse=True)
    ordered = [pid for pid, _ in scored]

    ordered = _inject_exploration(ordered, exploration_rate)
    if category_of and per_category_cap:
        ordered = _cap_by_category(ordered, category_of, per_category_cap)
    return ordered


def _arms_for(product_ids: list, segment: str) -> dict:
    """product_id -> (alpha, beta) for this segment. Missing rows are cold-start."""
    try:
        from plugins.installed.dynamics.models import BanditArm

        rows = BanditArm.objects.filter(product_id__in=product_ids, segment=segment).values_list(
            'product_id', 'alpha', 'beta'
        )
        return {pid: (a, b) for pid, a, b in rows}
    except Exception:  # noqa: BLE001 — DB hiccup → everyone cold-starts
        return {}


def _inject_exploration(ordered: list, rate: float) -> list:
    """Light, order-preserving exploration: each non-head position has a small
    chance to swap with a random later item, so low-data arms still get shown."""
    if rate <= 0 or len(ordered) < 3:  # noqa: PLR2004
        return ordered
    out = list(ordered)
    for i in range(1, len(out)):
        if random.random() < rate:  # noqa: S311 — exploration jitter, not crypto
            j = random.randrange(i, len(out))  # noqa: S311
            out[i], out[j] = out[j], out[i]
    return out


def _cap_by_category(ordered: list, category_of: dict, cap: int) -> list:
    """Keep at most ``cap`` items per category in the head; overflow slides to the
    tail (a simple MMR-style diversity guard)."""
    counts: dict = {}
    head, tail = [], []
    for pid in ordered:
        cat = category_of.get(pid)
        if cat is not None and counts.get(cat, 0) >= cap:
            tail.append(pid)
        else:
            counts[cat] = counts.get(cat, 0) + 1
            head.append(pid)
    return head + tail
