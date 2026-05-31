"""Versioned LLM prompt templates.

Each template is a function returning a string — never a raw constant —
so we can interpolate context without f-string-injection risk and so
callers can swap version by importing a different function.

Versioning convention: `RECOMMEND_V1`, `RECOMMEND_V2`, etc. Old
versions stay importable so older recommendations can be replayed
under their original prompt for audit + eval.
"""

from __future__ import annotations

import json
from typing import Any

# Bumped when the recommend prompt schema changes. Stored on
# SiRecommendation.model_id so an eval task can replay under the
# original template.
RECOMMEND_PROMPT_VERSION = 'recommend_v1'


def recommend_v1(
    *,
    module: str,
    recommendation_class: str,
    customization_summary: str,
    signal_summary: str,
    file_excerpts: str,
    prior_fixes_summary: str,
    reversibility: bool,
    auto_threshold: float,
    protected_paths: list[str],
) -> str:
    """The canonical recommend prompt. Returns a string ready to send."""
    protected_paths_str = '\n  '.join(protected_paths) or '(none)'
    return f"""\
SYSTEM: You are a senior Django + e-commerce engineer reviewing a single
cluster of signals from a Morpheus shop. Output strict JSON matching the
schema. Be falsifiable. Cite evidence by signal_id. If unsure, set
confidence below 0.5 and propose `advise` not `open_pr`.

CONTEXT
- Module: {module}
- Class: {recommendation_class}
- Customization status of affected files:
{customization_summary or '  (no declared customizations)'}
- Signal cluster ({_count(signal_summary)} signals):
{signal_summary or '  (none)'}
- Affected file excerpts (50-line windows):
{file_excerpts or '  (no file context retrieved)'}
- Episodic memory (prior similar):
{prior_fixes_summary or '  (none)'}
- Policy for this class:
  reversibility={reversibility}, auto_threshold={auto_threshold:.2f}

REQUIRED OUTPUT (JSON, no prose):
{{
  "title": "<=80 chars, imperative",
  "rationale": "<=600 chars, cites signal_ids",
  "confidence": 0.0-1.0,
  "impact_score": 0-1000,
  "is_customization_safe": true|false,
  "proposed_action": {{
    "kind": "advise" | "apply_data" | "open_pr",
    "files": ["path/relative/to/repo/..."],
    "patch": "unified diff or null",
    "test_command": "pytest path -k ..."
  }},
  "uncertainty_flags": ["..."],
  "rollback_cost": "trivial" | "moderate" | "high"
}}

HARD RULES
- Never propose changes inside any of these paths:
  {protected_paths_str}
- Never modify migrations.
- Never propose changes to files declared `intentional` above
  unless the class is `upstream_sync`.
- Never add a new top-level import not already in poetry.lock.
- If the change touches > 5 files or > 200 lines, downgrade to `advise`.
"""


VERIFY_PROMPT_VERSION = 'verify_v1'


def verify_v1(*, recommendation: dict[str, Any]) -> str:
    """Adversarial verifier prompt. Different framing from recommend_v1
    so the verifier can disagree."""
    return f"""\
SYSTEM: You are a skeptical staff engineer reviewing a proposed
recommendation from a code-improvement system. Default to refuted=true
when uncertain. Output strict JSON.

CANDIDATE RECOMMENDATION
{json.dumps(recommendation, default=str, indent=2)}

CHECKLIST
1. Does the rationale cite the evidence signal_ids?
2. Does the proposed patch (if any) plausibly resolve every signal
   in the evidence_signal_ids set?
3. Are there clear false-positive scenarios for this class of fix?
4. Does the patch introduce its own risks (race conditions, security
   regressions, new dependencies)?
5. Is `is_customization_safe` consistent with what you can see in
   the customization summary?
6. Is the confidence calibrated, or inflated?

OUTPUT (JSON):
{{
  "refuted": true|false,
  "reasons": ["..."],          // why refuted, or why confirmed
  "calibrated_confidence": 0.0-1.0,
  "recommend_downgrade_to": "advise" | "open_pr" | null
}}
"""


WEEKLY_DIGEST_PROMPT_VERSION = 'digest_v1'


def weekly_digest_v1(
    *, accepted: int, rejected: int, rollback_rate: float, top_classes: list[dict]
) -> str:
    """Tiny prompt for the weekly digest email body. The LLM has just
    enough freedom to add narrative + recommendations."""
    return f"""\
Generate a 4-paragraph weekly digest email for the engineering team
about the self-improvement engine's activity this week.

Inputs:
- accepted = {accepted}
- rejected = {rejected}
- rollback_rate = {rollback_rate:.1%}
- top classes by volume: {json.dumps(top_classes, default=str)}

Tone: factual, no marketing. Include: (1) what the engine did,
(2) which classes are working well, (3) which classes need policy
re-tuning, (4) the single highest-leverage suggestion for next week.
Output plain text, no markdown headers.
"""


# ---------------------------------------------------------------------------


def _count(blob: str) -> int:
    """How many signal rows are summarised in the blob (heuristic — counts
    newlines). Used only for context labelling in the prompt."""
    return blob.count('\n') + 1 if blob else 0
