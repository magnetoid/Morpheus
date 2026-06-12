"""Smoke test for returns_portal plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.returns_portal.plugin import ReturnsPortalPlugin

    assert ReturnsPortalPlugin.name == 'returns_portal'
    assert 'orders' in ReturnsPortalPlugin.requires


def test_default_resolution_is_exchange():
    from plugins.installed.returns_portal.plugin import ReturnsPortalPlugin

    schema = ReturnsPortalPlugin().get_config_schema()
    assert schema['properties']['default_resolution']['default'] == 'exchange'
