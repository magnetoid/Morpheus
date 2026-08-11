"""Smoke test for rich_post_purchase plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.rich_post_purchase.app import RichPostPurchasePlugin

    assert RichPostPurchasePlugin.name == 'rich_post_purchase'
