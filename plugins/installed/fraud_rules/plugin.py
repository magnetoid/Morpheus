"""Fraud-rules plugin manifest."""

from __future__ import annotations

from morpheus.plugin import Plugin, SettingsPanel


class FraudRulesPlugin(Plugin):
    name = 'fraud_rules'
    label = 'Fraud rules'
    version = '1.0.0'
    description = (
        'Lightweight risk scoring layered on top of Stripe Radar. '
        'Velocity, address mismatch, BIN denylist, refund history.'
    )

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Fraud rules',
            category='developer',
            description='Tune the merchant-specific thresholds.',
            schema={
                'high_risk_bins': {
                    'type': 'array',
                    'title': 'High-risk BIN list',
                    'description': (
                        'First 6 digits of cards that auto-flag as high risk. '
                        'Populate after a Stripe Radar review identifies known '
                        'attacker patterns.'
                    ),
                    'items': {'type': 'string'},
                    'default': [],
                },
                'high_value_threshold': {
                    'type': 'number',
                    'title': 'High-value threshold (USD)',
                    'minimum': 0,
                    'default': 500,
                },
                'auto_reject_at_score': {
                    'type': 'integer',
                    'title': 'Auto-reject score (Phase 2 — off by default)',
                    'minimum': 60,
                    'maximum': 100,
                    'default': 100,
                    'description': (
                        'Phase 2 will move orders ≥ this score into a review '
                        'queue and emit cancellation alerts. Phase 1 only logs.'
                    ),
                },
            },
        )
