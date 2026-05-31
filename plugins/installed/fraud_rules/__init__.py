"""Fraud-rules plugin — lightweight risk scoring on every ORDER_PLACED.

Layered on top of Stripe Radar (which only sees the card transaction).
We score against velocity, address mismatch, BIN risk, and refund
history — signals the payment processor can't see because they live
in our DB.

Output: a risk score 0-100 written to order.metadata['fraud_score']
and a flag list. Optional: hook subscribers can move high-risk orders
into a review queue (off by default — emits warnings only in Phase 1).
"""

default_app_config = 'plugins.installed.fraud_rules.apps.FraudRulesConfig'
