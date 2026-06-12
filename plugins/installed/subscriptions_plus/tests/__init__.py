"""Smoke test for subscriptions_plus plugin."""
from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.subscriptions_plus.plugin import SubscriptionsPlusPlugin
    assert SubscriptionsPlusPlugin.name == 'subscriptions_plus'
    assert 'orders' in SubscriptionsPlusPlugin.requires


def test_default_cadence():
    from plugins.installed.subscriptions_plus.plugin import SubscriptionsPlusPlugin
    schema = SubscriptionsPlusPlugin().get_config_schema()
    assert schema['properties']['default_cadence_days']['default'] == 30
