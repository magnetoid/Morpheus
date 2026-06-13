"""Multi-model consensus review for agent-drafted code (uplift Phase 5).

A model judging its OWN output rubber-stamps it — it shares its own blind spots.
So a CodeProposal is reviewed by SEVERAL configured LLM providers independently
and a quorum decides. Degrades safely: with fewer than two providers configured
it returns ``insufficient`` and defers to human review (never a false "approved").

This is advisory only — consensus never auto-approves a proposal; a human still
gates whether code goes live. Pure-ish: the LLM calls are the only side effect.
"""

# Lazy provider imports keep this load-order-safe; per-provider failures are
# swallowed so one bad reviewer can't abort the panel.
# ruff: noqa: PLC0415, S112

from __future__ import annotations

import json
import logging

logger = logging.getLogger('morpheus.assistant.consensus')

# Provider order to poll. ollama/mock excluded — local/test backends aren't
# independent reviewers. Capped so a panel is a few diverse models, not all 8.
_PREFERRED = ('anthropic', 'openai', 'gemini', 'grok', 'hermes', 'openrouter', 'packy')
_MAX_PANEL = 4
_QUORUM_NUM, _QUORUM_DEN = 2, 3  # approve if >= 2/3 of valid reviewers approve

_REVIEW_SYSTEM = (
    'You are a strict, senior Python code reviewer for a Django e-commerce platform. '
    'Review the proposed agent-tool module for correctness, security (injection, '
    'unsafe calls, hallucinated imports), and whether it does what its rationale '
    'claims. Reply ONLY with compact JSON: '
    '{"approve": true|false, "score": 0-10, "concerns": ["..."]}.'
)


def configured_providers() -> list[str]:
    """Names of providers that actually have an API key — the consensus panel."""
    out: list[str] = []
    try:
        from core.agents.provider_registry import get_provider_config
    except Exception:  # noqa: BLE001
        return out
    for name in _PREFERRED:
        try:
            if (get_provider_config(name).api_key or '').strip():
                out.append(name)
        except Exception:  # noqa: BLE001
            continue
    return out


def _review_prompt(proposal) -> str:
    return (
        f'Tool name: {proposal.name}\n'
        f'Rationale: {proposal.rationale or "(none)"}\n'
        f'Static-scan findings: {json.dumps(proposal.findings or [])}\n\n'
        f'SOURCE:\n```python\n{proposal.source}\n```'
    )


def _parse_verdict(provider: str, text: str) -> dict:
    """Pull the {approve,score,concerns} JSON out of a model reply. Fail-soft:
    an unparseable reply is marked not-ok so it doesn't count toward quorum."""
    raw = (text or '').strip()
    start, end = raw.find('{'), raw.rfind('}')
    if start != -1 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            return {
                'provider': provider,
                'ok': True,
                'approve': bool(data.get('approve')),
                'score': data.get('score'),
                'concerns': data.get('concerns') or [],
            }
        except (json.JSONDecodeError, TypeError):
            pass
    return {'provider': provider, 'ok': False, 'approve': False, 'error': 'unparseable reply'}


def review_with(provider_name: str, proposal) -> dict:
    """One provider's independent verdict on the proposal. Fail-soft per provider."""
    try:
        from core.agents.llm import LLMMessage, get_llm_provider

        provider = get_llm_provider(provider_name)
        resp = provider.respond(
            messages=[
                LLMMessage(role='system', content=_REVIEW_SYSTEM),
                LLMMessage(role='user', content=_review_prompt(proposal)),
            ],
            temperature=0.0,
            max_tokens=500,
        )
        return _parse_verdict(provider_name, resp.text)
    except Exception as e:  # noqa: BLE001 — one provider failing must not abort the panel
        logger.debug('consensus: provider %s failed: %s', provider_name, e)
        return {'provider': provider_name, 'ok': False, 'approve': False, 'error': str(e)[:120]}


def aggregate(verdicts: list[dict]) -> dict:
    """Decide from a list of verdicts. <2 valid → insufficient (defer to human)."""
    valid = [v for v in verdicts if v.get('ok')]
    n = len(valid)
    approvals = sum(1 for v in valid if v.get('approve'))
    if n < 2:
        decision = 'insufficient'
    elif approvals * _QUORUM_DEN >= n * _QUORUM_NUM:
        decision = 'approved'
    else:
        decision = 'rejected'
    concerns = sorted({c for v in valid for c in (v.get('concerns') or [])})
    return {
        'decision': decision,
        'providers': n,
        'approvals': approvals,
        'concerns': concerns,
        'verdicts': verdicts,
    }


def evaluate(proposal) -> dict:
    """Run the full consensus panel over a proposal (advisory; no side effects on
    the proposal itself — the caller persists the result)."""
    names = configured_providers()
    if len(names) < 2:
        return {
            'decision': 'insufficient',
            'providers': len(names),
            'note': 'need >=2 configured LLM providers for consensus — human review required',
            'verdicts': [],
        }
    verdicts = [review_with(name, proposal) for name in names[:_MAX_PANEL]]
    return aggregate(verdicts)
