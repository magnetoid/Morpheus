"""Token → USD cost estimation (`core/agents/pricing.py`)."""

from __future__ import annotations

from django.test import SimpleTestCase

from core.agents.pricing import estimate_cost, is_priced


class PricingTests(SimpleTestCase):
    def test_known_model_cost(self):
        # gpt-4o-mini: $0.15/1M in, $0.60/1M out.
        cost = estimate_cost('gpt-4o-mini', 1_000_000, 1_000_000)
        self.assertAlmostEqual(cost, 0.75, places=4)

    def test_dated_suffix_matches_base_price(self):
        a = estimate_cost('claude-3-5-sonnet-20241022', 1_000_000, 0)
        b = estimate_cost('claude-3-5-sonnet', 1_000_000, 0)
        self.assertEqual(a, b)
        self.assertAlmostEqual(a, 3.0, places=4)

    def test_unknown_model_is_zero(self):
        self.assertEqual(estimate_cost('mystery-model-9000', 1000, 1000), 0.0)
        self.assertFalse(is_priced('mystery-model-9000'))

    def test_local_model_is_free(self):
        self.assertTrue(is_priced('llama3.2'))
        self.assertEqual(estimate_cost('llama3.2', 5_000_000, 5_000_000), 0.0)

    def test_negative_tokens_floored(self):
        self.assertEqual(estimate_cost('gpt-4o-mini', -10, -10), 0.0)

    def test_every_default_provider_model_is_priced(self):
        # An unpriced default drops the provider from Linda's model picker and
        # from the backup list without a word (janus_engine filters on
        # is_priced), and the spend cap sees $0 for every turn it serves.
        from core.agents.provider_registry import _DEFAULT_MODELS

        for provider, model in _DEFAULT_MODELS.items():
            with self.subTest(provider=provider, model=model):
                self.assertTrue(is_priced(model))

    def test_vendor_prefix_and_dots_match_the_dashed_key(self):
        # OpenRouter names models 'vendor/name' and writes versions with dots.
        self.assertEqual(
            estimate_cost('anthropic/claude-3.5-sonnet', 1_000_000, 0),
            estimate_cost('claude-3-5-sonnet', 1_000_000, 0),
        )
        self.assertTrue(is_priced('openai/gpt-4.1-mini'))
        self.assertTrue(is_priced('gpt-4.1-mini'))
