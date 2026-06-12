"""Smoke test for smart_shipping plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.smart_shipping.plugin import SmartShippingPlugin

    assert SmartShippingPlugin.name == 'smart_shipping'
    assert 'shipping' in SmartShippingPlugin.requires
