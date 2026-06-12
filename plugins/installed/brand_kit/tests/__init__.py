"""Smoke test for brand_kit plugin."""
from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.brand_kit.plugin import BrandKitPlugin
    assert BrandKitPlugin.name == 'brand_kit'
