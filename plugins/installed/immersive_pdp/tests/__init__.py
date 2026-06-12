"""Smoke test for immersive_pdp plugin."""
from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.immersive_pdp.plugin import ImmersivePdpPlugin
    assert ImmersivePdpPlugin.name == 'immersive_pdp'
    assert 'catalog' in ImmersivePdpPlugin.requires


def test_block_count_default():
    from plugins.installed.immersive_pdp.plugin import ImmersivePdpPlugin
    schema = ImmersivePdpPlugin().get_config_schema()
    assert schema['properties']['story_block_count']['default'] == 3
