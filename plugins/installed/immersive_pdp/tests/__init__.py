"""Smoke test for immersive_pdp plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.immersive_pdp.plugin import ImmersivePdpPlugin

    assert ImmersivePdpPlugin.name == 'immersive_pdp'
    assert 'catalog' in ImmersivePdpPlugin.requires


def test_sticky_buybox_default_on():
    from plugins.installed.immersive_pdp.plugin import ImmersivePdpPlugin

    schema = ImmersivePdpPlugin().get_config_schema()
    assert schema['properties']['sticky_buybox']['default'] is True


def test_only_pdp_buybox_blocks_contributed():
    from plugins.installed.immersive_pdp.plugin import ImmersivePdpPlugin

    slots = {b.slot for b in ImmersivePdpPlugin().contribute_storefront_blocks()}
    assert slots == {'pdp_below_form', 'global_below_body'}
