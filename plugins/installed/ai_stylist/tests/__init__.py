"""Smoke test for ai_stylist plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.ai_stylist.plugin import AiStylistPlugin

    assert AiStylistPlugin.name == 'ai_stylist'
    assert 'ai_assistant' in AiStylistPlugin.requires
