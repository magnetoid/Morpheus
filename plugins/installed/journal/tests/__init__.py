"""Smoke test for journal plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.journal.app import JournalPlugin

    assert JournalPlugin.name == 'journal'
    assert 'cms' in JournalPlugin.requires
