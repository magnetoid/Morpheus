"""Adversarial verifier — second LLM, different prompt, default-refuted.

Run after the analyzer proposes a recommendation. If the verifier
returns `refuted=true`, the recommendation is downgraded to `advise`
(or suppressed entirely if the calibrated confidence drops below the
class's propose threshold).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from core.self_improvement.prompts import VERIFY_PROMPT_VERSION, verify_v1

logger = logging.getLogger('morpheus.self_improvement.verify')


@dataclass(slots=True)
class VerifyResult:
    refuted: bool
    reasons: list
    calibrated_confidence: float
    recommend_downgrade_to: str | None
    raw_response: str = ''


def verify_recommendation(recommendation: dict) -> VerifyResult:
    """Run the adversarial check; fail-open on errors.

    Fail-open means: if the verifier provider is unreachable or returns
    malformed output, we DO NOT silently approve a high-stakes change.
    Instead we downgrade to `advise` and flag the failure in the
    rationale so the engineer can review.
    """
    try:
        from core.agents.llm import LLMMessage  # noqa: PLC0415
        from core.assistant.providers import get_default_provider  # noqa: PLC0415

        provider = get_default_provider()
        if provider is None:
            return _fail_open('no_provider')

        prompt = verify_v1(recommendation=recommendation)
        # Kernel providers expose `respond()` only — there is no `complete()`.
        response = provider.respond(
            messages=[
                LLMMessage(role='system', content='You output strict JSON.'),
                LLMMessage(role='user', content=prompt),
            ],
            max_tokens=600,
            temperature=0.0,
        )
        text = (getattr(response, 'text', '') or '').strip()
        parsed = _parse_json(text)
        if parsed is None:
            return _fail_open('parse_error', raw=text)

        return VerifyResult(
            refuted=bool(parsed.get('refuted', True)),
            reasons=list(parsed.get('reasons') or []),
            calibrated_confidence=float(parsed.get('calibrated_confidence', 0.0)),
            recommend_downgrade_to=parsed.get('recommend_downgrade_to'),
            raw_response=text[:2000],
        )
    except Exception:  # noqa: BLE001
        logger.exception('verify_recommendation failed')
        return _fail_open('exception')


def _fail_open(reason: str, raw: str = '') -> VerifyResult:
    return VerifyResult(
        refuted=True,
        reasons=[f'verifier_unavailable:{reason}'],
        calibrated_confidence=0.0,
        recommend_downgrade_to='advise',
        raw_response=raw,
    )


def _parse_json(text: str):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        # Try to find the first {...} block in case the model added prose.
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except (ValueError, TypeError):
                return None
        return None


__all__ = ['VERIFY_PROMPT_VERSION', 'VerifyResult', 'verify_recommendation']
