"""Smoke test for journal plugin."""
from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.journal.plugin import JournalPlugin
    assert JournalPlugin.name == 'journal'
    assert 'cms' in JournalPlugin.requires


def test_default_block_types():
    from plugins.installed.journal.plugin import JournalPlugin
    schema = JournalPlugin().get_config_schema()
    defaults = schema['properties']['allow_block_types']['default']
    assert 'product' in defaults
    assert 'video' in defaults
