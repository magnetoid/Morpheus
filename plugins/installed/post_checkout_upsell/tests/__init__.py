"""Smoke test for post_checkout_upsell plugin."""
from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.post_checkout_upsell.plugin import PostCheckoutUpsellPlugin
    assert PostCheckoutUpsellPlugin.name == 'post_checkout_upsell'
