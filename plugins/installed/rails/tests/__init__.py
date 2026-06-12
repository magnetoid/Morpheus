"""Smoke test for rails plugin."""
from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.rails.plugin import RailsPlugin
    assert RailsPlugin.name == 'rails'
    assert 'personalisation' in RailsPlugin.requires
