"""The analyzer + verifier must speak the kernel provider contract.

`recommend._plan` and `verify.verify_recommendation` called
`provider.complete(system=…, messages=…)` — a method no `core.agents.llm`
provider has (they expose `respond()` only). Every live run raised
`AttributeError: 'DeepSeekProvider' object has no attribute 'complete'`,
the broad except turned it into the heuristic plan / fail-open verdict, and
the self-improvement loop never used its LLM once. The existing tests only
patched the provider to `None`, so they never exercised the real contract;
these use the kernel's own `MockLLMProvider`.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from django.test import SimpleTestCase

from core.agents.llm import LLMResponse, MockLLMProvider
from core.self_improvement.policy import policy_for
from core.self_improvement.recommend import Cluster, _plan
from core.self_improvement.verify import verify_recommendation

_PROVIDER = 'core.assistant.providers.get_default_provider'


def _cluster() -> Cluster:
    return Cluster(
        class_name='test_llm_contract',
        fingerprint='fp-contract',
        severity=70,
        seen_count=5,
        age_hours=1.0,
        signal_ids=[1],
        payload_samples=[{}],
    )


class AnalyzerProviderContractTests(SimpleTestCase):
    def test_plan_uses_the_llm_answer(self) -> None:
        plan = {'title': 'LLM-written plan marker', 'confidence': 0.9, 'proposed_action': {}}
        provider = MockLLMProvider(
            [LLMResponse(text=json.dumps(plan), prompt_tokens=40, completion_tokens=2)]
        )
        with patch(_PROVIDER, return_value=provider):
            result = _plan(_cluster(), policy_for('test_llm_contract'))

        self.assertEqual(result['title'], 'LLM-written plan marker')
        self.assertNotIn('llm_unavailable', result.get('uncertainty_flags', []))
        self.assertEqual(result['_tokens_used'], 42)
        self.assertEqual(len(provider.calls), 1)
        roles = [m.role for m in provider.calls[0]['messages']]
        self.assertEqual(roles, ['system', 'user'])


class VerifierProviderContractTests(SimpleTestCase):
    def test_verdict_comes_from_the_llm(self) -> None:
        verdict = {'refuted': False, 'reasons': ['holds up'], 'calibrated_confidence': 0.8}
        provider = MockLLMProvider([LLMResponse(text=json.dumps(verdict))])
        with patch(_PROVIDER, return_value=provider):
            result = verify_recommendation({'title': 'x'})

        self.assertFalse(result.refuted)
        self.assertEqual(result.reasons, ['holds up'])
        self.assertEqual(result.calibrated_confidence, 0.8)
