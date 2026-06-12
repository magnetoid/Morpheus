"""Smoke test for lookbook plugin."""
from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.lookbook.plugin import LookbookPlugin
    assert LookbookPlugin.name == 'lookbook'
    assert 'catalog' in LookbookPlugin.requires
