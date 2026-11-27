"""Adversarial verifier — second LLM, different prompt, default-refuted.

Run after the analyzer proposes a recommendation. If the verifier returns
`refuted=true`, the analyzer caps the recommendation's confidence below every
propose threshold, so it is filed as advice and never applied unattended.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from celery.exceptions import SoftTimeLimitExceeded

from core.agents.guardrails import AIPaused
from core.llm_parsing import parse_llm_object
from core.self_improvement.prompts import VERIFY_PROMPT_VERSION, verify_v1

logger = logging.getLogger('morpheus.self_improvement.verify')


@dataclass(slots=True)
class VerifyResult:
    refuted: bool
    reasons: list
    calibrated_confidence: float
    recommend_downgrade_to: str | None
    raw_response: str = ''
    tokens_used: int = 0
    # The call itself failed (not: the model answered and refuted).
    failed: bool = False


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
            return unavailable('no_provider', failed=True)

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
        tokens = int(getattr(response, 'prompt_tokens', 0) or 0) + int(
            getattr(response, 'completion_tokens', 0) or 0
        )
        text = (getattr(response, 'text', '') or '').strip()
        parsed = parse_llm_object(text)
        if parsed is None:
            return unavailable('parse_error', raw=text, tokens_used=tokens)

        return VerifyResult(
            refuted=bool(parsed.get('refuted', True)),
            reasons=list(parsed.get('reasons') or []),
            calibrated_confidence=float(parsed.get('calibrated_confidence', 0.0)),
            recommend_downgrade_to=parsed.get('recommend_downgrade_to'),
            raw_response=text[:2000],
            tokens_used=tokens,
        )
    except SoftTimeLimitExceeded:
        raise
    except AIPaused as e:  # the merchant paused AI or hit today's cap: not a fault
        logger.info('verify_recommendation skipped the model: %s', e)
        return unavailable('ai_paused', failed=True)
    except Exception:  # noqa: BLE001
        logger.exception('verify_recommendation failed')
        return unavailable('exception', failed=True)


def unavailable(
    reason: str, raw: str = '', *, tokens_used: int = 0, failed: bool = False
) -> VerifyResult:
    """No verdict: counted as refuted, so nothing unverified is applied."""
    return VerifyResult(
        refuted=True,
        reasons=[f'verifier_unavailable:{reason}'],
        calibrated_confidence=0.0,
        recommend_downgrade_to='advise',
        raw_response=raw,
        tokens_used=tokens_used,
        failed=failed,
    )


__all__ = ['VERIFY_PROMPT_VERSION', 'VerifyResult', 'unavailable', 'verify_recommendation']
