"""Smoke test for save_for_later plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.save_for_later.plugin import SaveForLaterPlugin

    assert SaveForLaterPlugin.name == 'save_for_later'
    assert 'wishlist' in SaveForLaterPlugin.requires
