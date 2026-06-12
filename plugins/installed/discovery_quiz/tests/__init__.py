"""Smoke test for discovery_quiz plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.discovery_quiz.plugin import DiscoveryQuizPlugin

    assert DiscoveryQuizPlugin.name == 'discovery_quiz'
