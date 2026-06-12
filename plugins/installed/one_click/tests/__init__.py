"""Smoke test for one_click plugin."""
from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.one_click.plugin import OneClickPlugin
    assert OneClickPlugin.name == 'one_click'
    assert 'orders' in OneClickPlugin.requires
