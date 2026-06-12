"""Smoke test for media_3d plugin."""

from __future__ import annotations


def test_plugin_metadata():
    from plugins.installed.media_3d.plugin import Media3dPlugin

    assert Media3dPlugin.name == 'media_3d'
    assert 'catalog' in Media3dPlugin.requires


def test_max_glb_budget_default():
    from plugins.installed.media_3d.plugin import Media3dPlugin

    schema = Media3dPlugin().get_config_schema()
    assert schema['properties']['max_glb_size_mb']['default'] == 12
