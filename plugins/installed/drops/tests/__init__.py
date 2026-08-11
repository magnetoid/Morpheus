"""Smoke test for drops plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.drops.app import DropsPlugin

    assert DropsPlugin.name == 'drops'
    assert 'pwa' in DropsPlugin.requires
